import NextAuth from "next-auth"
import Google from "next-auth/providers/google"

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
  callbacks: {
    async jwt({ token, user }) {
      if (user) token.user = user;
      return token;
    },
    async session({ session, token }: any) {
      session.user = token.user;
      return session;
    },
  },
})