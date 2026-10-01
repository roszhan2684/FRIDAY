import { SignUp } from "@clerk/nextjs";

export default function SignUpPage() {
  return (
    <div className="min-h-screen bg-[#06060f] flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <span className="text-2xl font-bold gradient-text">FRIDAY</span>
          <p className="text-slate-400 mt-2 text-sm">Create your free account</p>
        </div>
        <SignUp
          appearance={{
            elements: {
              rootBox: "w-full",
              card: "bg-[#0d0d1a] border border-white/10 shadow-2xl rounded-2xl",
              headerTitle: "text-white",
              headerSubtitle: "text-slate-400",
              socialButtonsBlockButton: "bg-white/5 border border-white/10 text-white hover:bg-white/10",
              dividerLine: "bg-white/10",
              dividerText: "text-slate-500",
              formFieldLabel: "text-slate-300",
              formFieldInput: "bg-white/5 border-white/10 text-white placeholder-slate-500 focus:border-indigo-500",
              formButtonPrimary: "bg-indigo-600 hover:bg-indigo-500",
              footerActionLink: "text-indigo-400 hover:text-indigo-300",
            },
          }}
          redirectUrl="/app"
        />
      </div>
    </div>
  );
}
