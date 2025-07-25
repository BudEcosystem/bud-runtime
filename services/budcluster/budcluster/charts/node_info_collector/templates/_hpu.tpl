{{- define "node-info-collector-hpu" }}
- name: node-info-collector-hpu
  image: "{{ .device.image }}"
  imagePullPolicy: {{ .device.pullPolicy }}
  securityContext:
    privileged: true
  resources:
    {{- toYaml .device.resources | nindent 12 }}
  env:
    - name: POD_NAMESPACE
      valueFrom:
        fieldRef:
          fieldPath: metadata.namespace
    - name: KUBERNETES_CLUSTER_IP
      value: "$(KUBERNETES_SERVICE_HOST):$(KUBERNETES_SERVICE_PORT)"
{{- end }}
