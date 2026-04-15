"use client";

import Link from "next/link";
import { sendEvent } from "@/lib/gtm";

export function CtaLink({
  href,
  className,
  children,
}: {
  href: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={className}
      onClick={() => sendEvent("cta_click", { link: href })}
    >
      {children}
    </Link>
  );
}
