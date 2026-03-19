import type { Metadata } from "next";
import { Fira_Code } from "next/font/google";
import "./globals.css";
import { FloatingNav } from "@/components/FloatingNav";
import { Providers } from "@/components/Providers";

const firaCode = Fira_Code({
  variable: "--font-fira-code",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Sentient - Digital Civilization",
  description: "Observe a living digital species",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className={`${firaCode.variable} font-mono antialiased bg-[#050505] text-[#e8e8e8]`}>
        <Providers>
          <FloatingNav />
          <main className="min-h-screen">
            {children}
          </main>
        </Providers>
      </body>
    </html>
  );
}
