import type { NextAuthOptions } from "next-auth";
import Auth0Provider from "next-auth/providers/auth0";
import GoogleProvider from "next-auth/providers/google";
import Credentials from "next-auth/providers/credentials";
import { prisma } from "./prisma";
import { verifyPassword } from "./password";

const useAuth0 =
  !!process.env.AUTH0_CLIENT_ID &&
  !!process.env.AUTH0_CLIENT_SECRET &&
  !!process.env.AUTH0_ISSUER;

const mockAuthEnabled = process.env.MOCK_AUTH_ENABLED !== "false";

const providers = [];
if (useAuth0) {
  providers.push(
    Auth0Provider({
      clientId: process.env.AUTH0_CLIENT_ID as string,
      clientSecret: process.env.AUTH0_CLIENT_SECRET as string,
      issuer: process.env.AUTH0_ISSUER as string,
    })
  );
}

const useGoogle = !!process.env.GOOGLE_CLIENT_ID && !!process.env.GOOGLE_CLIENT_SECRET;
if (useGoogle) {
  providers.push(
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID as string,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET as string,
    })
  );
}

const localAuthEnabled = process.env.LOCAL_AUTH_ENABLED !== "false";
if (localAuthEnabled) {
  providers.push(
    Credentials({
      id: "local",
      name: "Email or Username",
      credentials: {
        identifier: { label: "Email or username", type: "text" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const identifier = credentials?.identifier?.trim();
        const password = credentials?.password ?? "";
        if (!identifier || !password) {
          return null;
        }
        const user = (await prisma.user.findFirst({
          where: {
            OR: [{ email: identifier.toLowerCase() }, { username: identifier }],
          },
        } as any)) as
          | {
              id: string;
              netid: string | null;
              email: string | null;
              username: string | null;
              passwordHash: string | null;
            }
          | null;
        if (!user?.passwordHash) {
          return null;
        }
        const ok = await verifyPassword(password, user.passwordHash);
        if (!ok) {
          return null;
        }
        const userId = user.netid ?? user.email ?? user.id;
        return {
          id: userId,
          name: user.username ?? user.email ?? user.netid ?? "RUPlanner User",
          email: user.email ?? undefined,
        };
      },
    })
  );
}

if (mockAuthEnabled) {
  providers.push(
    Credentials({
      name: "NetID (Mock)",
      credentials: {
        netid: { label: "NetID", type: "text" },
      },
      async authorize(credentials) {
        const netid = credentials?.netid?.trim();
        if (!netid) {
          return null;
        }
        return { id: netid, name: netid, email: `${netid}@rutgers.edu` };
      },
    })
  );
}

export const authOptions: NextAuthOptions = {
  session: { strategy: "jwt" },
  useSecureCookies: process.env.NODE_ENV === "production",
  providers,
  callbacks: {
    async jwt({ token, user, profile }) {
      if (user?.id) {
        token.netid = user.id;
      }
      if (!token.netid && user?.email) {
        token.netid = user.email;
      }
      const profileNetId = (profile as { netid?: string } | null)?.netid;
      if (profileNetId) {
        token.netid = profileNetId;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user && token.netid) {
        (session.user as { id: string }).id = token.netid as string;
      }
      return session;
    },
  },
};
