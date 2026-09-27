import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "Tender Agent | Live workspace", description: "Follow real tender analysis from document to human decision support." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" data-scroll-behavior="smooth"><body>{children}</body></html>;
}
