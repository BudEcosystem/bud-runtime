/**
 * Format cost value with appropriate decimal places.
 * Shows 4 decimal places for small values (< $0.01), otherwise 2 decimal places.
 */
export const formatCost = (cost: number | null | undefined): string => {
  if (cost === null || cost === undefined || isNaN(cost)) {
    return "0.00";
  }
  return cost < 0.01 ? cost.toFixed(4) : cost.toFixed(2);
};
