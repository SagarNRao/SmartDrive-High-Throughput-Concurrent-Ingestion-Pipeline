import { auth, signIn } from "./auth"
import { redirect } from "next/navigation"

export default async function LoginPage() {
  const session = await auth()
  
  if (session) {
    redirect("/dashboard")
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-neutral-900 text-white">
      <h1 className="text-4xl font-bold mb-4">Smart Google Drive Engine</h1>
      <p className="text-gray-400 mb-8">Securely log in to map and index your documents.</p>
      <form
        action={async () => {
          "use server"
          await signIn("google", { redirectTo: "/dashboard" })
        }}
      >
        <button className="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-medium transition-all">
          Sign In with Google
        </button>
      </form>
    </div>
  )
}