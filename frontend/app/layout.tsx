import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "PathNovo MTO Generator | Isometric Drawing Analyser",
  description:
    "Upload a piping isometric drawing and instantly generate a structured Material Take-Off (MTO) using AI vision extraction.",
  keywords: ["MTO", "Material Take-Off", "piping isometric", "AI extraction", "engineering"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="antialiased">{children}</body>
    </html>
  );
}
