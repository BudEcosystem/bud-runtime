import { Form } from "antd";
import { useEffect, useState } from "react";

export function useForm({ initialData }: { initialData: any }) {
  const [form] = Form.useForm();
  const [submittable, setSubmittable] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (initialData) {
      form.setFieldsValue(initialData);
    }
  }, []);

  // Watch all values
  const values = Form.useWatch([], form);
  useEffect(() => {
    form
      .validateFields({
        validateOnly: true,
        dirty: true,
      })
      .then((result) => {
        setSubmittable(true);
      })
      .catch(() => setSubmittable(false));
  }, [form, values]);

  return {
    form,
    submittable,
    loading,
    setLoading,
    values,
  };
}