// Centralized constants for blocking rules to improve maintainability

export const RULE_TYPE_VALUES = {
  IP_BLOCKING: 'ip_blocking',
  COUNTRY_BLOCKING: 'country_blocking',
  USER_AGENT_BLOCKING: 'user_agent_blocking',
  RATE_BASED_BLOCKING: 'rate_based_blocking',
} as const;

export const RULE_TYPE_LABELS = {
  [RULE_TYPE_VALUES.IP_BLOCKING]: 'IP Blocking',
  [RULE_TYPE_VALUES.COUNTRY_BLOCKING]: 'Country Blocking',
  [RULE_TYPE_VALUES.USER_AGENT_BLOCKING]: 'User Agent Blocking',
  [RULE_TYPE_VALUES.RATE_BASED_BLOCKING]: 'Rate Based Blocking',
} as const;

export const RULE_TYPE_COLORS = {
  [RULE_TYPE_VALUES.IP_BLOCKING]: 'blue',
  [RULE_TYPE_VALUES.COUNTRY_BLOCKING]: 'green',
  [RULE_TYPE_VALUES.USER_AGENT_BLOCKING]: 'orange',
  [RULE_TYPE_VALUES.RATE_BASED_BLOCKING]: 'red',
} as const;

export const RULE_STATUS_VALUES = {
  ACTIVE: 'ACTIVE',
  INACTIVE: 'INACTIVE',
  EXPIRED: 'EXPIRED',
} as const;

export const RULE_STATUS_COLORS: any = {
  [RULE_STATUS_VALUES.ACTIVE]: 'green',
  [RULE_STATUS_VALUES.INACTIVE]: 'orange',
  [RULE_STATUS_VALUES.EXPIRED]: 'red',
} as const;

// Country codes for country blocking
export const COUNTRY_CODES = [
  { code: 'US', name: 'United States' },
  { code: 'CN', name: 'China' },
  { code: 'RU', name: 'Russia' },
  { code: 'IN', name: 'India' },
  { code: 'JP', name: 'Japan' },
  { code: 'DE', name: 'Germany' },
  { code: 'GB', name: 'United Kingdom' },
  { code: 'FR', name: 'France' },
  { code: 'BR', name: 'Brazil' },
  { code: 'CA', name: 'Canada' },
  { code: 'AU', name: 'Australia' },
  { code: 'KR', name: 'South Korea' },
  { code: 'MX', name: 'Mexico' },
  { code: 'ES', name: 'Spain' },
  { code: 'IT', name: 'Italy' },
];

// Helper function to get rule type display label
export const getRuleTypeLabel = (type: string): string => {
  return RULE_TYPE_LABELS[type as keyof typeof RULE_TYPE_LABELS] || type;
};

// Helper function to get rule type color
export const getRuleTypeColor = (type: string): string => {
  return RULE_TYPE_COLORS[type as keyof typeof RULE_TYPE_COLORS] || 'default';
};

// Helper function to get status color
export const getStatusColor = (status: string): string => {
  return RULE_STATUS_COLORS[status as keyof typeof RULE_STATUS_COLORS] || 'default';
};
