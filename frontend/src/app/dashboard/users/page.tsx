"use client";

import { useEffect, useState, useCallback } from "react";
import { useLanguage } from "@/contexts/language-context";
import { useToast } from "@/hooks/useToast";
import { apiClient } from "@/lib/auth-api";
import { getErrorMessage } from "@/lib/error-utils";
import { ToastContainer } from "@/components/ui/Toast";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { UserFormModal } from "@/components/users/UserFormModal";
import { Plus, Search, Edit, Trash2 } from "lucide-react";


interface CurrentUser {
  user_id: string;
  email: string;
  role: string;
  full_name: string;
}

interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  last_login: string | null;
  created_at: string;
}

export default function UsersPage() {
  const { t } = useLanguage();
  const toast = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [showFormModal, setShowFormModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [userToDelete, setUserToDelete] = useState<User | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    const fetchCurrentUser = async () => {
      try {
        const response = await apiClient.get("/auth/me");
        setCurrentUser(response.data);
      } catch (error) {
        console.error("Failed to fetch current user:", error);
      }
    };
    fetchCurrentUser();
  }, []);

  const fetchUsers = useCallback(async () => {
    try {
      setLoading(true);
      const response = await apiClient.get("/admin/users");
      setUsers(response.data);
    } catch (error: unknown) {
      console.error("Failed to fetch users:", error);
      toast.error(getErrorMessage(error, t("common.error"), t));
    } finally {
      setLoading(false);
    }
  }, [t, toast]);

  useEffect(() => {
    fetchUsers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const isRoot = currentUser?.role === "root";
  const isAdmin = currentUser?.role === "admin";
  const canEdit = (user: User) => {
    if (isRoot) return true;
    if (isAdmin) return user.id === currentUser?.user_id;
    return user.id === currentUser?.user_id;
  };
  const canDelete = (user: User) => {
    if (!isRoot) return false;
    if (user.role === "root") return false;
    if (user.id === currentUser?.user_id) return false;
    return true;
  };
  const canCreate = isRoot || isAdmin;

  const handleCreateUser = async (data: { email: string; full_name: string; role: string }) => {
    try {
      await apiClient.post("/admin/users", data);
      toast.success(t("users.userCreated"));
      fetchUsers();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("common.error"), t));
      throw error;
    }
  };

  const handleUpdateUser = async (data: { email?: string; full_name?: string; role?: string }) => {
    if (!selectedUser) return;

    try {
      await apiClient.put(`/admin/users/${selectedUser.id}`, data);
      toast.success(t("users.userUpdated"));
      fetchUsers();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("common.error"), t));
      throw error;
    }
  };

  const handleDeleteUser = async () => {
    if (!userToDelete) return;

    try {
      await apiClient.delete(`/admin/users/${userToDelete.id}`);
      toast.success(t("users.userDeleted"));
      fetchUsers();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("common.error"), t));
    } finally {
      setUserToDelete(null);
    }
  };

  const filteredUsers = users.filter((user) =>
    user.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
    user.full_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "-";
    return new Date(dateString).toLocaleDateString();
  };

  return (
    <div className="space-y-6">
      <ToastContainer toasts={toast.toasts} onClose={toast.removeToast} />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">{t("users.title")}</h1>
          <p className="text-gray-600 mt-1">{t("users.manageUsers")}</p>
        </div>
      </div>

      {/* Search */}
      <div className="card">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 pointer-events-none" />
          <input
            type="text"
            placeholder={t("common.search")}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input-field input-with-icon"
          />
        </div>
      </div>

      {/* Users Table */}
      <div className="card overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("users.email")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("users.fullName")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("users.role")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("users.status")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("users.lastLogin")}
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("users.actions")}
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                    {t("common.loading")}
                  </td>
                </tr>
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                    {t("users.noUsers")}
                  </td>
                </tr>
              ) : (
                filteredUsers.map((user) => (
                  <tr key={user.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {user.email}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {user.full_name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="badge badge-info">
                        {user.role}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`badge ${user.is_active ? "badge-success" : "badge-error"} `}>
                        {user.is_active ? t("users.active") : t("users.inactive")}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(user.last_login)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => {
                            setSelectedUser(user);
                            setShowFormModal(true);
                          }}
                          disabled={!canEdit(user)}
                          className="text-[var(--color-primary)] hover:text-[var(--color-primary-dark)] disabled:opacity-30 disabled:cursor-not-allowed"
                          title={t("users.edit")}
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => setUserToDelete(user)}
                          disabled={!canDelete(user)}
                          className="text-red-600 hover:text-red-700 disabled:opacity-30 disabled:cursor-not-allowed"
                          title={t("users.delete")}
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* User Form Modal */}
      <UserFormModal
        isOpen={showFormModal}
        onClose={() => {
          setShowFormModal(false);
          setSelectedUser(null);
        }}
        onSubmit={selectedUser ? handleUpdateUser : handleCreateUser}
        user={selectedUser}
        currentUser={currentUser ? { id: currentUser.user_id, role: currentUser.role } : null}
      />

      {/* Delete Confirmation */}
      <ConfirmDialog
        isOpen={!!userToDelete}
        onClose={() => setUserToDelete(null)}
        onConfirm={handleDeleteUser}
        title={t("users.delete")}
        message={t("users.confirmDelete")}
        confirmText={t("common.delete")}
        cancelText={t("common.cancel")}
        type="danger"
      />
    </div>
  );
}

