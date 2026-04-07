import { NextResponse } from "next/server";
import { readDashboardStatus } from "@/lib/status";

export async function GET() {
  return NextResponse.json(readDashboardStatus());
}
