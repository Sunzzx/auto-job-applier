from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError, async_playwright

from job_agent.models import AgentPolicy, ApplyAction, ApplyOutcome, JobPosting, JobProfile, JobStatus, utc_now


class BrowserApplyAgent:
    def __init__(self, profile: JobProfile, policy: AgentPolicy) -> None:
        self.profile = profile
        self.policy = policy
        self.artifacts_dir = Path(policy.artifacts_dir).expanduser()
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.linkedin_storage_state = Path(policy.linkedin_storage_state_path).expanduser()
        self.linkedin_storage_state.parent.mkdir(parents=True, exist_ok=True)
        self.known_values = {k.lower(): v for k, v in profile.known_field_values().items() if v}

    async def run(self, job: JobPosting, action: ApplyAction) -> ApplyOutcome:
        domain = urlparse(str(job.url)).netloc.lower()
        context_kwargs = {}
        if "linkedin.com" in domain and self.linkedin_storage_state.exists():
            context_kwargs["storage_state"] = str(self.linkedin_storage_state)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.policy.headless_browser)
            context = await browser.new_context(**context_kwargs)
            page = await context.new_page()
            outcome = await self._execute(page, context, browser, job, action)
            await browser.close()
            return outcome

    async def login_linkedin(self) -> str:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_timeout(1000)
            linkedin_email = os.getenv("LINKEDIN_EMAIL") or self.profile.identity.email
            linkedin_password = os.getenv("LINKEDIN_PASSWORD")

            if linkedin_password:
                await self._fill_first_match(page, ["input[name='session_key']", "input[type='email']", "input[name*='email']"], linkedin_email)
                await self._fill_first_match(page, ["input[name='session_password']", "input[type='password']"], linkedin_password)
                submit = page.locator("button[type='submit'], input[type='submit']").first
                if await submit.count() > 0:
                    await submit.click()
                    await page.wait_for_timeout(5000)
            else:
                await asyncio.to_thread(
                    input,
                    "LinkedIn login opened. Sign in manually in the browser, then press Enter here to save session... ",
                )
            await context.storage_state(path=str(self.linkedin_storage_state))
            await browser.close()
        return str(self.linkedin_storage_state)

    async def _execute(
        self,
        page: Page,
        context: BrowserContext,
        browser: Browser,
        job: JobPosting,
        action: ApplyAction,
    ) -> ApplyOutcome:
        del context, browser
        notes: list[str] = []
        screenshot_paths: list[str] = []
        try:
            await page.goto(str(job.url), wait_until="domcontentloaded", timeout=45_000)
            await page.wait_for_timeout(1500)
        except PlaywrightTimeoutError:
            path = await self._snap(page, job, "timeout")
            screenshot_paths.append(path)
            return ApplyOutcome(
                job,
                action,
                JobStatus.blocked,
                ["Navigation timed out before the page loaded."],
                screenshot_paths,
                blocker_type="navigation_timeout",
                blocker_signals=["timeout"],
            )
        except Exception as exc:  # noqa: BLE001
            path = await self._snap(page, job, "navigation-error")
            screenshot_paths.append(path)
            return ApplyOutcome(
                job,
                action,
                JobStatus.blocked,
                [f"Navigation failed: {exc}"],
                screenshot_paths,
                blocker_type="navigation_error",
                blocker_signals=[type(exc).__name__],
            )

        domain = urlparse(str(job.url)).netloc.lower()
        if "linkedin.com" in domain and not self.linkedin_storage_state.exists():
            path = await self._snap(page, job, "linkedin-login-required")
            screenshot_paths.append(path)
            return ApplyOutcome(
                job,
                action,
                JobStatus.blocked,
                ["LinkedIn session is missing. Run `job-agent linkedin-login` and sign in manually."],
                screenshot_paths,
                blocker_type="auth_required",
                blocker_signals=["linkedin_login_required"],
            )

        title = await page.title()
        blocker_type, blocker_signals = self._detect_blockers(await page.content())
        if blocker_type is not None:
            path = await self._snap(page, job, "blocked")
            screenshot_paths.append(path)
            return ApplyOutcome(
                job,
                action,
                JobStatus.blocked,
                [f"Blocked by anti-bot gate: {blocker_type}."],
                screenshot_paths,
                blocker_type=blocker_type,
                blocker_signals=blocker_signals,
            )

        notes.append(f"Opened page: {title}")
        screenshot_paths.append(await self._snap(page, job, "opened"))

        if action == ApplyAction.preview:
            return ApplyOutcome(job, action, JobStatus.previewed, notes, screenshot_paths)

        missing = await self._fill_known_fields(page, notes)
        if self.policy.auto_upload_resume:
            await self._upload_resume_if_present(page, notes)
        screenshot_paths.append(await self._snap(page, job, "filled"))

        if missing and self.policy.stop_on_missing_answers:
            notes.append(f"Missing answers prevented escalation: {', '.join(sorted(set(missing))[:10])}")
            return ApplyOutcome(
                job,
                action,
                JobStatus.blocked,
                notes,
                screenshot_paths,
                blocker_type="missing_answers",
                blocker_signals=sorted(set(missing))[:20],
            )

        if action == ApplyAction.fill:
            return ApplyOutcome(job, action, JobStatus.filled, notes, screenshot_paths)

        domain = urlparse(str(job.url)).netloc.lower()
        if self.policy.submit_mode != "autonomous" and domain not in self.policy.allow_domains_for_submit:
            notes.append(f"Submit skipped because domain is not allow-listed: {domain}")
            return ApplyOutcome(job, action, JobStatus.filled, notes, screenshot_paths)

        submit_button, submit_selector = await self._find_submit_button(page)
        if submit_button is None:
            notes.append("Submit button not found.")
            return ApplyOutcome(
                job,
                action,
                JobStatus.blocked,
                notes,
                screenshot_paths,
                blocker_type="submit_not_found",
                blocker_signals=["no_submit_button"],
            )

        await submit_button.click()
        await page.wait_for_timeout(2000)
        screenshot_paths.append(await self._snap(page, job, "submitted"))
        notes.append(f"Submit attempted via selector: {submit_selector}")
        return ApplyOutcome(job, action, JobStatus.submitted, notes, screenshot_paths, submitted_at=utc_now())

    async def _find_submit_button(self, page: Page):
        selectors = [
            "button[type=submit], input[type=submit]",
            "button:has-text('Submit')",
            "button:has-text('Apply')",
            "button:has-text('Send application')",
            "button:has-text('Continue')",
            "[role='button']:has-text('Submit')",
            "[role='button']:has-text('Apply')",
        ]
        for selector in selectors:
            locator = page.locator(selector).first
            if await locator.count() == 0:
                continue
            try:
                if await locator.is_visible():
                    return locator, selector
            except Exception:  # noqa: BLE001
                continue
        return None, None

    def _detect_blockers(self, html: str) -> tuple[str | None, list[str]]:
        lowered = html.lower()
        checks: list[tuple[str, list[str]]] = [
            ("captcha", ["captcha", "recaptcha", "hcaptcha", "turnstile"]),
            ("otp", ["one-time password", "otp", "verification code", "2fa"]),
            ("botwall", ["verify you are human", "are you human", "security check", "cloudflare"]),
        ]
        for blocker_type, tokens in checks:
            matched = [token for token in tokens if token in lowered]
            if matched:
                return blocker_type, matched
        return None, []

    async def _fill_known_fields(self, page: Page, notes: list[str]) -> list[str]:
        unresolved: list[str] = []
        fields = page.locator("input, textarea, select")
        count = await fields.count()
        for index in range(count):
            field = fields.nth(index)
            if not await field.is_visible():
                continue
            input_type = (await field.get_attribute("type") or "").lower()
            name = (await field.get_attribute("name") or "").lower()
            placeholder = (await field.get_attribute("placeholder") or "").lower()
            aria = (await field.get_attribute("aria-label") or "").lower()
            label_text = " ".join([name, placeholder, aria]).strip()

            if input_type in {"hidden", "submit", "button", "file"}:
                continue

            mapped_value = self._lookup_value(label_text)
            if mapped_value is None:
                if await field.get_attribute("required") is not None:
                    unresolved.append(label_text or f"field-{index}")
                continue

            try:
                tag_name = await field.evaluate("(el) => el.tagName.toLowerCase()")
                if tag_name == "select":
                    await field.select_option(label=mapped_value)
                elif input_type in {"checkbox", "radio"}:
                    if mapped_value.strip().lower() in {"yes", "true", "1"}:
                        await field.check()
                else:
                    await field.fill(mapped_value)
                notes.append(f"Filled {label_text or f'field-{index}'}")
            except Exception as exc:  # noqa: BLE001
                notes.append(f"Could not fill {label_text or f'field-{index}'}: {exc}")
        return unresolved

    def _lookup_value(self, label_text: str) -> str | None:
        label_text = label_text.lower()
        aliases = {
            "full name": "full_name",
            "name": "name",
            "email": "email",
            "phone": "phone",
            "mobile": "phone",
            "city": "location",
            "location": "location",
            "linkedin": "linkedin",
            "github": "github",
            "portfolio": "portfolio",
            "website": "website",
            "experience": "years_of_experience",
            "current title": "current_title",
            "sponsorship": "sponsorship_required",
            "relocate": "willing_to_relocate",
            "expected": "expected_ctc",
            "notice": "notice_period",
        }
        for needle, key in aliases.items():
            if needle in label_text:
                return self.known_values.get(key.lower())
        slug = re.sub(r"[^a-z0-9]+", "_", label_text).strip("_")
        return self.known_values.get(slug.lower())

    async def _upload_resume_if_present(self, page: Page, notes: list[str]) -> None:
        resume = self.profile.resume_file()
        if not resume.exists():
            notes.append(f"Resume file not found: {resume}")
            return
        uploads = page.locator("input[type=file]")
        count = await uploads.count()
        for index in range(count):
            field = uploads.nth(index)
            if not await field.is_visible():
                continue
            try:
                await field.set_input_files(str(resume))
                notes.append(f"Uploaded resume into file input {index}")
                return
            except Exception as exc:  # noqa: BLE001
                notes.append(f"Resume upload failed on input {index}: {exc}")

    async def _fill_first_match(self, page: Page, selectors: list[str], value: str) -> bool:
        for selector in selectors:
            locator = page.locator(selector).first
            if await locator.count() == 0:
                continue
            try:
                await locator.fill(value)
                return True
            except Exception:  # noqa: BLE001
                continue
        return False

    async def _snap(self, page: Page, job: JobPosting, label: str) -> str:
        safe_key = job.dedupe_key().replace("/", "_").replace(":", "_")
        path = self.artifacts_dir / f"{safe_key}-{label}.png"
        await page.screenshot(path=str(path), full_page=True)
        return str(path)
