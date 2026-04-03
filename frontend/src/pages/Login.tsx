import { useAuth } from "@/context/auth";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

const ERROR_MESSAGES: Record<string, string> = {
  access_denied: "Access was denied. Please try again.",
  missing_params: "Authentication failed. Please try again.",
  invalid_state: "Session expired. Please try again.",
  token_exchange_failed: "Authentication failed. Please try again.",
  no_id_token: "Authentication failed. Please try again.",
  invalid_id_token: "Authentication failed. Please try again.",
  email_not_verified: "Your Google email is not verified.",
  domain_not_allowed: "Your email domain is not allowed to sign in.",
  account_mismatch: "This email is linked to a different Google account.",
};

export default function Login() {
  const { loginFromCallback, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Handle OAuth callback — tokens arrive in the URL fragment
    const hash = window.location.hash.substring(1);
    if (!hash) return;

    // Clear the hash immediately so tokens aren't visible in the address bar
    window.history.replaceState(null, "", window.location.pathname);

    const params = new URLSearchParams(hash);
    const callbackError = params.get("error");
    if (callbackError) {
      setError(ERROR_MESSAGES[callbackError] ?? "An unknown error occurred.");
      return;
    }

    const accessToken = params.get("access_token");
    const refreshToken = params.get("refresh_token");
    if (accessToken && refreshToken) {
      loginFromCallback(accessToken, refreshToken);
      navigate("/", { replace: true });
    }
  }, [loginFromCallback, navigate]);

  // Already logged in — redirect handled by the route guard, but avoid flash
  useEffect(() => {
    if (isAuthenticated) navigate("/", { replace: true });
  }, [isAuthenticated, navigate]);

  const handleGoogleLogin = () => {
    const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
    window.location.href = `${apiUrl}/api/v1/auth/google/login`;
  };

  return (
    <div className="flex min-h-screen">
      {/* Left panel — brand */}
      <div
        className="relative hidden w-1/2 items-center justify-center overflow-hidden lg:flex"
        style={{ background: "hsl(310 7% 14%)" }}
      >
        <div
          className="absolute inset-0 opacity-[0.04]"
          style={{
            backgroundImage:
              "linear-gradient(hsl(25 30% 97%) 1px, transparent 1px), linear-gradient(90deg, hsl(25 30% 97%) 1px, transparent 1px)",
            backgroundSize: "60px 60px",
          }}
        />
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 60% 50% at 50% 50%, hsla(36, 90%, 55%, 0.08) 0%, transparent 80%)",
          }}
        />
        <div className="relative z-10 max-w-sm px-12 text-center animate-enter">
          <img
            src="/fresk-logo-dark.svg"
            alt="fresk.digital"
            className="mx-auto mb-8 h-10 w-auto brightness-0 invert"
          />
          <h1
            className="text-3xl tracking-tight text-white/90"
            style={{ fontFamily: '"DM Serif Display", Georgia, serif' }}
          >
            Sales Intelligence,
            <br />
            Refined.
          </h1>
          <p className="mt-4 text-sm leading-relaxed text-white/40">
            Discover high-intent leads, monitor buying signals, and close deals
            faster with AI-powered pipeline intelligence.
          </p>
        </div>
      </div>

      {/* Right panel — sign in */}
      <div className="flex flex-1 items-center justify-center bg-background px-6">
        <div className="w-full max-w-sm animate-enter-up">
          {/* Mobile logo */}
          <div className="mb-8 flex justify-center lg:hidden">
            <img
              src="/fresk-logo-dark.svg"
              alt="fresk.digital"
              className="h-8 w-auto"
            />
          </div>

          <div className="mb-8 hidden lg:block">
            <h2
              className="text-2xl text-foreground"
              style={{ fontFamily: '"DM Serif Display", Georgia, serif' }}
            >
              Welcome back
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Sign in with your Google account to continue.
            </p>
          </div>

          {error && (
            <p className="mb-5 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}

          <button
            type="button"
            onClick={handleGoogleLogin}
            className="flex w-full items-center justify-center gap-3 rounded-lg border border-input bg-card px-4 py-2.5 text-sm font-medium shadow-sm transition-all duration-200 hover:bg-accent hover:shadow-md active:scale-[0.98]"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24">
              <path
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
                fill="#4285F4"
              />
              <path
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                fill="#34A853"
              />
              <path
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                fill="#FBBC05"
              />
              <path
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                fill="#EA4335"
              />
            </svg>
            Sign in with Google
          </button>
        </div>
      </div>
    </div>
  );
}
