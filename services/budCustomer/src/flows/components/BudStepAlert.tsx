"use client";

import React from "react";

interface BudStepAlertProps {
  children?: React.ReactNode;
  type?: "info" | "warning" | "error" | "success";
  className?: string;
  title?: string;
  description?: string;
  cancelAction?: () => void;
  confirmAction?: () => Promise<void> | void;
  confirmText?: string;
  cancelText?: string;
}

const BudStepAlert: React.FC<BudStepAlertProps> = ({
  children,
  type = "info",
  className = "",
  title,
  description,
  cancelAction,
  confirmAction,
  confirmText = "Confirm",
  cancelText = "Cancel"
}) => {
  return (
    <div className={`p-4 rounded-lg ${className}`}>
      {title && <div className="font-semibold text-white mb-2">{title}</div>}
      {description && <div className="text-gray-300 mb-4">{description}</div>}
      {children}
      {(cancelAction || confirmAction) && (
        <div className="flex gap-2 mt-4">
          {cancelAction && (
            <button
              onClick={cancelAction}
              className="px-3 py-1 bg-gray-600 text-white rounded text-sm"
            >
              {cancelText}
            </button>
          )}
          {confirmAction && (
            <button
              onClick={confirmAction}
              className="px-3 py-1 bg-red-600 text-white rounded text-sm"
            >
              {confirmText}
            </button>
          )}
        </div>
      )}
    </div>
  );
};

export default BudStepAlert;
