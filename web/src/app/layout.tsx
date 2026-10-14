import type { Metadata } from "next";
import { Fraunces, JetBrains_Mono } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CairnBooks — Kinetic EPUB 3 & Kindle KFX Footnote Compiler",
  description:
    "Eliminate reader confusion in dense fiction with zero-spoiler EPUB 3 & Kindle Paperwhite KFX popup footnotes.",
};

const publishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ?? "";
const isClerkConfigured =
  publishableKey.startsWith("pk_") &&
  !publishableKey.includes("your_clerk_key_here");

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const content = (
    <html
      lang="en"
      className={`${fraunces.variable} ${jetbrainsMono.variable}`}
    >
      <body className="min-h-screen bg-newsprint text-ink font-serif antialiased selection:bg-lime selection:text-ink">
        {children}
      </body>
    </html>
  );

  if (isClerkConfigured) {
    return <ClerkProvider publishableKey={publishableKey}>{content}</ClerkProvider>;
  }

  return content;
}
