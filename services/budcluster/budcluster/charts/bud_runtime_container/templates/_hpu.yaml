{{- define "bud-runtime-container.hpu-container" }}
{{- if not .Values.containerPort }}
{{- fail "Error: containerPort is not defined in values.yaml" }}
{{- end }}
- name: hpu-container
  image: {{ .device.image }}
  imagePullPolicy: {{ .Values.pullPolicy }}
  ports:
    - containerPort: {{ .Values.containerPort }}
  volumeMounts:
    - mountPath: /dev/shm
      name: shm
    - name: model-registry
      mountPath: /data/models-registry
      readOnly: false
  securityContext:
    allowPrivilegeEscalation: true
    runAsGroup: 0
    runAsUser: 0
  resources:
    requests:
      habana.ai/gaudi: {{ .device.tp_size }}
      memory: "{{ .device.memory }}Gi"
      cpu: {{ .device.core_count }}
    limits:
      habana.ai/gaudi: {{ .device.tp_size }}
  {{- if .device.envs }}
  env:
  {{- range $key, $value := .device.envs }}
  - name: {{ $key }}
    value: {{ $value | quote }}
  {{- end }}
  {{- end }}
  {{- if .device.args }}
  args:
  {{- range $key, $value := .device.args }}
  - {{ $value }}
  {{- end }}
  {{- end }}
  livenessProbe: null
  readinessProbe:
    httpGet:
      path: /health
      port: {{ .Values.containerPort}}
    initialDelaySeconds: 60
    periodSeconds: 5
{{- end }}
