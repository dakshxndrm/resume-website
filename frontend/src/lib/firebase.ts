/**
 * Firebase = identity ONLY (Google login). All app data lives in Postgres via the backend.
 * Fill NEXT_PUBLIC_FIREBASE_* in .env.local (see .env.local.example).
 */
import { initializeApp, getApps, type FirebaseApp } from "firebase/app";
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signOut as fbSignOut,
  onAuthStateChanged,
  type User,
} from "firebase/auth";

const config = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

export const firebaseEnabled = Boolean(config.apiKey);

let app: FirebaseApp | null = null;
function getApp(): FirebaseApp | null {
  if (!firebaseEnabled) return null;
  if (!app) app = getApps()[0] ?? initializeApp(config);
  return app;
}

export function getAuthSafe() {
  const a = getApp();
  return a ? getAuth(a) : null;
}

export async function signInWithGoogle(): Promise<User | null> {
  const auth = getAuthSafe();
  if (!auth) {
    console.warn("Firebase not configured — set NEXT_PUBLIC_FIREBASE_* env vars.");
    return null;
  }
  const provider = new GoogleAuthProvider();
  const cred = await signInWithPopup(auth, provider);
  return cred.user;
}

export async function signOut() {
  const auth = getAuthSafe();
  if (auth) await fbSignOut(auth);
}

export function watchAuth(cb: (user: User | null) => void) {
  const auth = getAuthSafe();
  if (!auth) {
    cb(null);
    return () => {};
  }
  return onAuthStateChanged(auth, cb);
}

/** Returns a fresh ID token, or null when signed out / Firebase unconfigured. */
export async function getIdTokenSafe(): Promise<string | null> {
  const auth = getAuthSafe();
  const user = auth?.currentUser;
  if (!user) return null;
  return user.getIdToken();
}
