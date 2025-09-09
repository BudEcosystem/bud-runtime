import { create } from "zustand";
import { AppRequest } from "@/services/api/requests";

export interface BillingAlert {
  id: string;
  user_id: string;
  name: string;
  alert_type: "token_usage" | "cost_usage";
  threshold_percent: number;
  last_triggered_at?: string;
  last_triggered_value?: number;
  last_notification_sent_at?: string;
  notification_failure_count: number;
  last_notification_error?: string;
  is_active: boolean;
  created_at: string;
  modified_at: string;
}

export interface CreateBillingAlertRequest {
  name: string;
  alert_type: "token_usage" | "cost_usage";
  threshold_percent: number;
}

export const useBillingAlerts = create<{
  alerts: BillingAlert[];
  loading: boolean;
  error: string | null;

  // Actions
  getBillingAlerts: () => Promise<BillingAlert[]>;
  createBillingAlert: (
    data: CreateBillingAlertRequest,
  ) => Promise<BillingAlert>;
  updateBillingAlertStatus: (
    alertId: string,
    isActive: boolean,
  ) => Promise<BillingAlert>;
  deleteBillingAlert: (alertId: string) => Promise<boolean>;
  clearError: () => void;
}>((set, get) => ({
  alerts: [],
  loading: false,
  error: null,

  getBillingAlerts: async () => {
    set({ loading: true, error: null });
    try {
      const response = await AppRequest.Get("/billing/alerts");
      const alertsData = response.data.result || [];
      set({ alerts: alertsData, loading: false });
      return alertsData;
    } catch (error: any) {
      const errorMessage =
        error?.response?.data?.message ||
        error?.message ||
        "Failed to fetch billing alerts";
      set({ error: errorMessage, loading: false, alerts: [] });
      console.error("Error fetching billing alerts:", error);
      throw new Error(errorMessage);
    }
  },

  createBillingAlert: async (data: CreateBillingAlertRequest) => {
    set({ loading: true, error: null });
    try {
      const response = await AppRequest.Post("/billing/alerts", data);
      const newAlert = response.data.result;

      if (newAlert) {
        // Refresh the alerts list
        await get().getBillingAlerts();
      }

      set({ loading: false });
      return newAlert;
    } catch (error: any) {
      const errorMessage =
        error?.response?.data?.message ||
        error?.message ||
        "Failed to create billing alert";
      set({ error: errorMessage, loading: false });
      console.error("Error creating billing alert:", error);
      throw new Error(errorMessage);
    }
  },

  updateBillingAlertStatus: async (alertId: string, isActive: boolean) => {
    set({ loading: true, error: null });
    try {
      const response = await AppRequest.Put(`/billing/alerts/${alertId}`, {
        is_active: isActive,
      });
      const updatedAlert = response.data.result;

      if (updatedAlert) {
        // Update the specific alert in the list
        const currentAlerts = get().alerts;
        const updatedAlerts = currentAlerts.map((alert) =>
          alert.id === alertId ? { ...alert, is_active: isActive } : alert,
        );
        set({ alerts: updatedAlerts });
      }

      set({ loading: false });
      return updatedAlert;
    } catch (error: any) {
      const errorMessage =
        error?.response?.data?.message ||
        error?.message ||
        "Failed to update billing alert status";
      set({ error: errorMessage, loading: false });
      console.error("Error updating billing alert status:", error);
      throw new Error(errorMessage);
    }
  },

  deleteBillingAlert: async (alertId: string) => {
    set({ loading: true, error: null });
    try {
      await AppRequest.Delete(`/billing/alerts/${alertId}`);

      // Remove the alert from the list
      const currentAlerts = get().alerts;
      const updatedAlerts = currentAlerts.filter(
        (alert) => alert.id !== alertId,
      );
      set({ alerts: updatedAlerts, loading: false });

      return true;
    } catch (error: any) {
      const errorMessage =
        error?.response?.data?.message ||
        error?.message ||
        "Failed to delete billing alert";
      set({ error: errorMessage, loading: false });
      console.error("Error deleting billing alert:", error);
      throw new Error(errorMessage);
    }
  },

  clearError: () => {
    set({ error: null });
  },
}));
