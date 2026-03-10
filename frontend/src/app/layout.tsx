import "./globals.css";
export const metadata = {
  title: "RU Planner",
  description: "Rutgers degree planner",
  icons: {
    icon: [{ url: "/RUPlanner_logo.png", sizes: "any" }],
    apple: "/RUPlanner_logo.png",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
