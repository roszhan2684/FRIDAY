import { auth, currentUser } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { getReminders, getShoppingList } from "@/lib/db";
import DashboardClient from "./DashboardClient";

export default async function DashboardPage() {
  const { userId } = await auth();
  if (!userId) redirect("/sign-in");

  const user = await currentUser();

  const [reminders, shopping] = await Promise.all([
    getReminders(userId, "upcoming"),
    getShoppingList(userId),
  ]);

  return (
    <DashboardClient
      user={{ name: user?.firstName ?? "Boss", email: user?.emailAddresses[0]?.emailAddress ?? "" }}
      reminders={reminders as { id: string; text: string; due_at: string | null; status: string }[]}
      shopping={shopping  as { id: string; item: string; store: string | null; quantity: string | null; checked: boolean }[]}
    />
  );
}
