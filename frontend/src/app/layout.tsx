import type { Metadata } from "next";
import "./globals.css";

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
    <html lang="en">
      <body>
        {children}
      </body>
    </html>
  );
}
