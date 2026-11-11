import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../app/AuthContext";
import { apiGet, apiPost } from "../services/api";
import { AuthGate } from "./AuthGate";

vi.mock("../services/api", () => ({ apiGet: vi.fn(), apiPost: vi.fn() }));
const password = "a-long-test-password";
const delivered = { message: "Check your email for a verification code.", verification_required: true, resend_after_seconds: 60 };

afterEach(cleanup);
beforeEach(() => {
  vi.resetAllMocks(); sessionStorage.clear();
  vi.mocked(apiPost).mockResolvedValue(delivered);
  vi.mocked(apiGet).mockResolvedValue({ id: "user-1", email: "new@example.com", email_verified: true });
});

async function openRegistration() {
  render(<AuthProvider><AuthGate><p>Private portfolio</p></AuthGate></AuthProvider>);
  await userEvent.click(await screen.findByRole("button", { name: "New here? Create an account" }));
  await userEvent.type(screen.getByLabelText("Email address"), "new@example.com");
  await userEvent.type(screen.getByLabelText("Password", { exact: true }), password);
  await userEvent.type(screen.getByLabelText("Confirm password"), password);
}

describe("account registration and verification", () => {
  it("creates an account and signs in without email when verification is paused", async () => {
    await openRegistration();
    vi.mocked(apiPost).mockResolvedValueOnce({ message: "Account created.", verification_required: false, resend_after_seconds: 0 })
      .mockResolvedValueOnce({ access_token: "registered-token" });
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Private portfolio")).toBeTruthy();
    expect(apiPost).toHaveBeenNthCalledWith(1, "/auth/register", { email: "new@example.com", password, confirm_password: password });
    expect(apiPost).toHaveBeenNthCalledWith(2, "/auth/login", { email: "new@example.com", password });
    expect(apiPost).toHaveBeenCalledTimes(2);
    expect(sessionStorage.getItem("northstar_access_token")).toBe("registered-token");
  });
  it("masks both passwords and lets users reveal and hide each without submitting", async () => {
    await openRegistration();
    const input = screen.getByLabelText("Password", { exact: true }) as HTMLInputElement;
    const confirmation = screen.getByLabelText("Confirm password") as HTMLInputElement;
    expect(input.type).toBe("password"); expect(confirmation.type).toBe("password");
    await userEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(input.type).toBe("text"); expect(input.value).toBe(password);
    expect(confirmation.type).toBe("password");
    await userEvent.click(screen.getByRole("button", { name: "Show confirmed password" }));
    expect(confirmation.type).toBe("text"); expect(confirmation.value).toBe(password);
    await userEvent.click(screen.getByRole("button", { name: "Hide password" }));
    await userEvent.click(screen.getByRole("button", { name: "Hide confirmed password" }));
    expect(input.type).toBe("password"); expect(confirmation.type).toBe("password");
    expect(apiPost).not.toHaveBeenCalled();
  });

  it("requires matching passwords before calling registration", async () => {
    await openRegistration();
    await userEvent.type(screen.getByLabelText("Confirm password"), "different");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Passwords do not match");
    expect(apiPost).not.toHaveBeenCalled();
  });

  it("opens the private portfolio only after email verification", async () => {
    await openRegistration();
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    await screen.findByRole("heading", { name: "Verify your email" });
    expect(apiPost).toHaveBeenCalledExactlyOnceWith("/auth/register", { email: "new@example.com", password, confirm_password: password });
    expect(sessionStorage.getItem("northstar_access_token")).toBeNull();
    expect(screen.queryByText("Private portfolio")).toBeNull();
    expect((screen.getByRole("button", { name: "Resend code in 60s" }) as HTMLButtonElement).disabled).toBe(true);
    vi.mocked(apiPost).mockResolvedValue({ access_token: "verified-token" });
    await userEvent.type(screen.getByLabelText("Email verification code"), "123456");
    await userEvent.click(screen.getByRole("button", { name: "Verify email and continue" }));
    expect(await screen.findByText("Private portfolio")).toBeTruthy();
    expect(apiPost).toHaveBeenLastCalledWith("/auth/verify-email", { email: "new@example.com", password, code: "123456" });
    expect(sessionStorage.getItem("northstar_access_token")).toBe("verified-token");
  });

  it("keeps users on verification when a code is rejected", async () => {
    await openRegistration();
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    await screen.findByRole("heading", { name: "Verify your email" });
    vi.mocked(apiPost).mockRejectedValue(new Error("Code is invalid or expired. Request a new code."));
    await userEvent.type(screen.getByLabelText("Email verification code"), "123456");
    await userEvent.click(screen.getByRole("button", { name: "Verify email and continue" }));
    expect((await screen.findByRole("alert")).textContent).toContain("invalid or expired");
    expect(sessionStorage.getItem("northstar_access_token")).toBeNull();
    expect(screen.queryByText("Private portfolio")).toBeNull();
  });

  it("allows an existing unverified user to request a code and handles cooldowns", async () => {
    render(<AuthProvider><AuthGate><p>Private portfolio</p></AuthGate></AuthProvider>);
    await userEvent.type(await screen.findByLabelText("Email address"), "existing@example.com");
    await userEvent.type(screen.getByLabelText("Password", { exact: true }), password);
    vi.mocked(apiPost).mockRejectedValueOnce(Object.assign(new Error("Verify your email before signing in."), { code: "email_verification_required" }));
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await screen.findByRole("heading", { name: "Verify your email" });
    vi.mocked(apiPost).mockRejectedValueOnce(Object.assign(new Error("Please wait one minute before requesting another code."), { retryAfter: 42 }));
    await userEvent.click(screen.getByRole("button", { name: "Send a new code" }));
    expect(apiPost).toHaveBeenLastCalledWith("/auth/resend-verification", { email: "existing@example.com", password });
    expect((await screen.findByRole("alert")).textContent).toContain("wait one minute");
    expect((screen.getByRole("button", { name: "Resend code in 42s" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("shows SMTP failures and lets users retry registration", async () => {
    await openRegistration();
    vi.mocked(apiPost).mockRejectedValueOnce(new Error("Email delivery is not configured."));
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect((await screen.findByRole("alert")).textContent).toContain("not configured");
    expect(screen.getByLabelText("Confirm password")).toBeTruthy();
    expect(sessionStorage.getItem("northstar_access_token")).toBeNull();
  });

  it("clears entered passwords and visibility when switching modes", async () => {
    await openRegistration();
    await userEvent.click(screen.getByRole("button", { name: "Show password" }));
    await userEvent.click(screen.getByRole("button", { name: "Already have an account? Sign in" }));
    expect((screen.getByLabelText("Password", { exact: true }) as HTMLInputElement).value).toBe("");
    expect((screen.getByLabelText("Password", { exact: true }) as HTMLInputElement).type).toBe("password");
    expect(screen.queryByLabelText("Confirm password")).toBeNull();
  });
});

