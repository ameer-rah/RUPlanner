import "./globals.css";

export const metadata = {
  title: "RU Planner",
  description: "Rutgers degree planner",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
