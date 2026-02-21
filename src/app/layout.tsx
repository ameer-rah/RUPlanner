import type { ReactNode } from "react";
import "./globals.css";

export const metadata = {
  title: "RUPlanner",
  description: "Rutgers degree planning demo",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="app-body">{children}</body>
    </html>
  );
}
