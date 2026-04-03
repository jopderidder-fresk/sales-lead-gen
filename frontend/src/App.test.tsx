import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import App from "./App";
import { AuthProvider } from "./context/auth";

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </QueryClientProvider>,
  );
}

test("renders login page when not authenticated", async () => {
  renderApp();
  expect(await screen.findByText("Sign in")).toBeInTheDocument();
});
