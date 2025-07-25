import { createContext } from "react";

export const BudFormContext = createContext({
  form: {} as any,
  submittable: false,
  loading: false,
  setLoading: (loading: boolean) => {},
  values: {} as any,
  isExpandedView: false,
  isExpandedViewOpen: false,
});