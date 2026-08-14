import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "RU Planner — Rutgers Degree Planning",
  description:
    "Plan your entire Rutgers–New Brunswick degree in minutes. Prerequisite-aware semester schedules, course sniping, and professor ratings — all in one place.",
  keywords: ["Rutgers", "degree planner", "course planner", "New Brunswick", "RU Planner", "WebReg"],
  icons: {
    icon: [
      { url: "/RUPlanner Web Design Ideas Favicon.svg", type: "image/svg+xml" },
    ],
    apple: "/RUPlanner Web Design Ideas Favicon.svg",
  },
  openGraph: {
    title: "RU Planner — Rutgers Degree Planning",
    description:
      "Plan your entire Rutgers–New Brunswick degree in minutes. Prerequisite-aware semester schedules, course sniping, and RMP ratings.",
    url: "https://ruplanner.app",
    siteName: "RU Planner",
    images: [
      {
        url: "/RUPlanner Logo.svg",
        width: 1200,
        height: 630,
        alt: "RU Planner",
      },
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "RU Planner — Rutgers Degree Planning",
    description:
      "Plan your entire Rutgers–New Brunswick degree in minutes.",
    images: ["/RUPlanner Logo.svg"],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body style={{ fontFamily: "var(--font-inter), 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" }}>
        {children}
      </body>
    </html>
  );
}
