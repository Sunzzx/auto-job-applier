from __future__ import annotations

import os
import smtplib
import subprocess
from email.message import EmailMessage

from job_agent.models import ApplyOutcome, EmailNotificationSettings, JobProfile


class EmailNotifier:
    def __init__(self, settings: EmailNotificationSettings, profile: JobProfile) -> None:
        self.settings = settings
        self.profile = profile

    def notify(self, outcome: ApplyOutcome) -> str:
        if not self.settings.enabled:
            return "Email notifications disabled"

        recipient = self.settings.recipient or self.profile.identity.email
        sender = self.settings.sender or self.profile.identity.email
        subject = self._subject(outcome)
        body = self._body(outcome)

        if self.settings.backend == "smtp":
            self._send_smtp(sender, recipient, subject, body)
            return f"SMTP email sent to {recipient}"

        self._send_mail_app(sender, recipient, subject, body)
        return f"Mail.app email queued to {recipient}"

    def _subject(self, outcome: ApplyOutcome) -> str:
        return (
            f"{self.settings.subject_prefix} {outcome.status.value.upper()}: "
            f"{outcome.job.company} - {outcome.job.title}"
        )

    def _body(self, outcome: ApplyOutcome) -> str:
        lines = [
            f"Company: {outcome.job.company}",
            f"Role: {outcome.job.title}",
            f"Source: {outcome.job.source}",
            f"Action: {outcome.action.value}",
            f"Status: {outcome.status.value}",
            f"Link: {outcome.job.url}",
        ]
        if outcome.submitted_at:
            lines.append(f"Submitted at: {outcome.submitted_at}")
        if self.settings.include_notes and outcome.notes:
            lines.append("")
            lines.append("Notes:")
            lines.extend(f"- {note}" for note in outcome.notes)
        if outcome.screenshot_paths:
            lines.append("")
            lines.append("Screenshots:")
            lines.extend(f"- {path}" for path in outcome.screenshot_paths)
        return "\n".join(lines)

    def _send_mail_app(self, sender: str, recipient: str, subject: str, body: str) -> None:
        apple_script = '''
        on run argv
            set theSubject to item 1 of argv
            set theBody to item 2 of argv
            set theRecipient to item 3 of argv
            set theSender to item 4 of argv

            tell application "Mail"
                set newMessage to make new outgoing message with properties {subject:theSubject, content:theBody & return, visible:false}
                tell newMessage
                    make new to recipient at end of to recipients with properties {address:theRecipient}
                    set sender to theSender
                    send
                end tell
            end tell
        end run
        '''
        subprocess.run(
            ["osascript", "-e", apple_script, subject, body, recipient, sender],
            check=True,
            timeout=self.settings.timeout_seconds,
        )

    def _send_smtp(self, sender: str, recipient: str, subject: str, body: str) -> None:
        if not self.settings.smtp_host:
            raise ValueError("SMTP backend selected but smtp_host is not configured")

        message = EmailMessage()
        message["From"] = sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)

        password = self.settings.smtp_password
        if not password and self.settings.smtp_password_env:
            password = os.getenv(self.settings.smtp_password_env)

        if self.settings.use_ssl:
            server = smtplib.SMTP_SSL(self.settings.smtp_host, self.settings.smtp_port, timeout=self.settings.timeout_seconds)
        else:
            server = smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=self.settings.timeout_seconds)

        with server as smtp:
            if self.settings.use_tls and not self.settings.use_ssl:
                smtp.starttls()
            if self.settings.smtp_username and password:
                smtp.login(self.settings.smtp_username, password)
            smtp.send_message(message)

    