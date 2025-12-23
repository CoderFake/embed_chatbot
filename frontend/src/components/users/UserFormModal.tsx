/**
 * User Create/Edit Modal
 */
"use client";

import { useEffect, useState, useMemo } from "react";
import { useLanguage } from "@/contexts/language-context";
import { useRoles } from "@/hooks/useRoles";
import { Modal } from "@/components/ui/Modal";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";

interface UserFormData {
  email: string;
  full_name: string;
  password?: string;
  role: string;
  is_active: boolean;
}

interface UserFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: UserFormData) => Promise<void>;
  user?: {
    id: string;
    email: string;
    full_name: string;
    role: string;
    is_active: boolean;
  } | null;
  currentUser?: {
    id: string;
    role: string;
  } | null;
}

export function UserFormModal({ isOpen, onClose, onSubmit, user, currentUser }: UserFormModalProps) {
  const { t } = useLanguage();
  const { roles, loading: rolesLoading } = useRoles();

  const isEditingSelf = user && currentUser && user.id === currentUser.id;
  const isRoot = currentUser?.role === "root";
  const isAdmin = currentUser?.role === "admin";
  const canChangeRole = isRoot && !isEditingSelf; 
  const availableRoles = useMemo(() => {
    if (isAdmin) {
      return roles.filter(role => role.value !== "root");
    }
    return roles;
  }, [roles, isAdmin]);

  const [formData, setFormData] = useState<UserFormData>({
    email: "",
    full_name: "",
    password: "",
    role: "member",
    is_active: true,
  });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (user) {
      setFormData({
        email: user.email,
        full_name: user.full_name,
        password: "",
        role: user.role,
        is_active: user.is_active,
      });
    } else {
      setFormData({
        email: "",
        full_name: "",
        password: "",
        role: "member",
        is_active: true,
      });
    }
  }, [user, isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      await onSubmit(formData);
      onClose();
    } catch {
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={user ? t("users.edit") : t("users.create")}
      size="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Email */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t("users.email")} *
          </label>
          <input
            type="email"
            value={formData.email}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            className="input-field"
            required
            disabled={!!user}
          />
        </div>

        {/* Full Name */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t("users.fullName")} *
          </label>
          <input
            type="text"
            value={formData.full_name}
            onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
            className="input-field"
            required
          />
        </div>

        {/* Password (only for create) */}
        {!user && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t("users.password")} *
            </label>
            <input
              type="password"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              className="input-field"
              required
              minLength={8}
            />
            <p className="text-xs text-gray-500 mt-1">Minimum 8 characters</p>
          </div>
        )}

        {/* Role */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t("users.role")} *
          </label>
          <select
            value={formData.role}
            onChange={(e) => setFormData({ ...formData, role: e.target.value })}
            className="input-field"
            disabled={rolesLoading || !canChangeRole}
            required
          >
            <option value="">{t("users.selectRole")}</option>
            {availableRoles.map((role) => (
              <option key={role.value} value={role.value}>
                {role.label}
              </option>
            ))}
          </select>
          {!canChangeRole && isEditingSelf && (
            <p className="text-xs text-gray-500 mt-1">
              {t("users.cannotChangeOwnRole")}
            </p>
          )}
        </div>

        {/* Status */}
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="is_active"
            checked={formData.is_active}
            onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
            className="w-4 h-4 text-[var(--color-primary)] border-gray-300 rounded"
            disabled={!!isEditingSelf}
          />
          <label htmlFor="is_active" className="text-sm font-medium text-gray-700">
            {t("users.active")}
          </label>
          {isEditingSelf && (
            <span className="text-xs text-gray-500 ml-2">
              ({t("users.cannotDeactivateSelf")})
            </span>
          )}
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-4">
          <button
            type="button"
            onClick={onClose}
            className="btn-outline"
            disabled={submitting}
          >
            {t("common.cancel")}
          </button>
          <button
            type="submit"
            className="btn-primary flex items-center gap-2"
            disabled={submitting}
          >
            {submitting ? (
              <>
                <LoadingSpinner size="sm" />
                {t("common.loading")}
              </>
            ) : user ? (
              t("common.save")
            ) : (
              t("common.create")
            )}
          </button>
        </div>
      </form>
    </Modal>
  );
}

