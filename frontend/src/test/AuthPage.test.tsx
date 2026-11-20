import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { AuthPage } from "../pages/AuthPage";

// Provide a minimal AuthContext
vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    signIn: vi.fn(),
    signUp: vi.fn(),
    user: null,
    loading: false,
    signOut: vi.fn(),
    deleteAccount: vi.fn(),
  }),
}));

vi.mock("../services/api", () => ({
  demoCredentials: { email: "demo@test.com", password: "demo" },
  useMocks: false,
  tokenKey: "scholar_token",
}));

function renderAuth(mode: "login" | "register") {
  return render(
    <BrowserRouter>
      <AuthPage mode={mode} />
    </BrowserRouter>
  );
}

describe("AuthPage", () => {
  it("renders login form with email and password fields", () => {
    renderAuth("login");
    expect(screen.getByPlaceholderText(/university\.edu/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/password/i)).toBeInTheDocument();
  });

  it("renders registration form with name and email fields", () => {
    renderAuth("register");
    expect(screen.getByPlaceholderText(/alex morgan/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/university\.edu/i)).toBeInTheDocument();
  });

  it("shows error when passwords do not match on register", async () => {
    renderAuth("register");

    const nameInput = screen.getByPlaceholderText(/alex morgan/i);
    const emailInput = screen.getByPlaceholderText(/university\.edu/i);
    // Find the password fields below.

    fireEvent.change(nameInput, { target: { value: "Test User" } });
    fireEvent.change(emailInput, { target: { value: "test@example.com" } });

    // Find password-type inputs
    const pwFields = screen
      .getByPlaceholderText(/university\.edu/i)
      .closest("form")
      ?.querySelectorAll('input[type="password"]');

    if (pwFields && pwFields.length >= 2) {
      fireEvent.change(pwFields[0], { target: { value: "password123" } });
      fireEvent.change(pwFields[1], { target: { value: "different" } });
    }

    const form = nameInput.closest("form");
    if (form) fireEvent.submit(form);

    // Should show mismatch error
    expect(
      await screen.findByText(/passwords do not match/i)
    ).toBeInTheDocument();
  });
});
