"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useLanguage } from "@/contexts/language-context";
import { apiClient } from "@/lib/auth-api";
import { Logo } from "@/components/Logo";
import { CheckCircle, XCircle, Loader2 } from "lucide-react";

export default function AcceptInvitePage() {
  const router = useRouter();
  const { t } = useLanguage();
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [email, setEmail] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string>("");

  const confirmInvite = useCallback(async (token: string) => {
    try {
      const response = await apiClient.post(
        `/admin/invites/confirm?token=${encodeURIComponent(token)}`
      );

      setEmail(response.data.email);
      setStatus("success");

      setTimeout(() => {
        router.push("/login");
      }, 3000);
    } catch (error: unknown) {
      setStatus("error");

      let message = t("invite.confirmFailed");
      if (error && typeof error === 'object' && 'response' in error) {
        const axiosError = error as { response?: { data?: { detail?: string | Array<{ msg: string }> } } };
        if (axiosError.response?.data?.detail) {
          if (typeof axiosError.response.data.detail === "string") {
            message = axiosError.response.data.detail;
          } else if (Array.isArray(axiosError.response.data.detail)) {
            message = axiosError.response.data.detail.map((e) => e.msg).join(", ");
          }
        }
      }
      setErrorMessage(message);
    }
  }, [router, t]);

  useEffect(() => {
    const hash = window.location.hash;
    let token = "";

    if (hash.startsWith("#token=")) {
      token = hash.substring(7);
    } else if (hash.startsWith("#")) {
      token = hash.substring(1);
    }

    if (!token) {
      setStatus("error");
      setErrorMessage(t("invite.missingToken"));
      return;
    }

    confirmInvite(token);
  }, [confirmInvite, t]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-50 via-white to-purple-50 px-4">
      <div className="max-w-md w-full">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-block transform hover:scale-105 transition-transform">
            <Logo variant="full" />
          </div>
        </div>

        {/* Card */}
        <div className="card text-center">
          {status === "loading" && (
            <>
              <div className="flex justify-center mb-4">
                <Loader2 className="w-16 h-16 text-indigo-600 animate-spin" />
              </div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">
                {t("invite.processing")}
              </h2>
              <p className="text-gray-600">
                {t("invite.pleaseWait")}
              </p>
            </>
          )}

          {status === "success" && (
            <>
              <div className="flex justify-center mb-4">
                <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
                  <CheckCircle className="w-10 h-10 text-green-600" />
                </div>
              </div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">
                {t("invite.success")}
              </h2>
              <p className="text-gray-600 mb-4">
                {t("invite.accountCreated")}
              </p>
              <div className="bg-gray-50 rounded-lg p-4 mb-6">
                <p className="text-sm text-gray-600 mb-1">
                  {t("invite.yourEmail")}
                </p>
                <p className="text-lg font-semibold text-gray-900">{email}</p>
              </div>
              <p className="text-sm text-gray-500">
                {t("invite.redirecting")}
              </p>
              <button
                onClick={() => router.push("/login")}
                className="btn-primary w-full mt-4"
              >
                {t("invite.goToLogin")}
              </button>
            </>
          )}

          {status === "error" && (
            <>
              <div className="flex justify-center mb-4">
                <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center">
                  <XCircle className="w-10 h-10 text-red-600" />
                </div>
              </div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">
                {t("invite.error")}
              </h2>
              <p className="text-gray-600 mb-6">
                {errorMessage}
              </p>
              <button
                onClick={() => router.push("/login")}
                className="btn-outline w-full"
              >
                {t("invite.backToLogin")}
              </button>
            </>
          )}
        </div>

        {/* Footer */}
        <p className="text-center text-sm text-gray-500 mt-6">
          {t("login.version")}
        </p>
      </div>
    </div>
  );
}

