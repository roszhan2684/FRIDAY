import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FRIDAY — AI Voice Assistant",
  description: "Your personal AI assistant. Talk to it. It gets things done.",
  openGraph: {
    title: "FRIDAY — AI Voice Assistant",
    description: "Your personal AI assistant. Talk to it. It gets things done.",
    type: "website",
  },
};

// Dynamically wrap with ClerkProvider only when a real key is present.
// During `next build` without credentials the app still compiles.
async function Providers({ children }: { children: React.ReactNode }) {
  const key = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ?? "";
  const hasClerk = key.startsWith("pk_live_") || key.startsWith("pk_test_eyJ");

  if (hasClerk) {
    const { ClerkProvider } = await import("@clerk/nextjs");
    return <ClerkProvider>{children}</ClerkProvider>;
  }
  return <>{children}</>;
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
