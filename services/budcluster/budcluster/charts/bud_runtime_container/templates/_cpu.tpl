{{- define "bud-runtime-container.cpu-container" }}
{{- if not .Values.containerPort }}
{{- fail "Error: containerPort is not defined in values.yaml" }}
{{- end }}
- name: cpu-container
  image: {{ .device.image }}
  imagePullPolicy: {{ .Values.pullPolicy }}
  ports:
    - containerPort: {{ .Values.containerPort }}
  volumeMounts:
    - name: model-registry
      mountPath: /data/models-registry
      readOnly: false
  resources:
    requests:
      memory: "{{ .device.memory }}Gi"
      cpu: {{ .device.core_count }}
    limits:
      memory: "{{ .device.memory }}Gi"
      cpu: {{ .device.core_count }}
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
  livenessProbe:
    httpGet:
      path: /health
      port: {{ .Values.containerPort}}
    initialDelaySeconds: 120
    periodSeconds: 30
  readinessProbe:
    httpGet:
      path: /health
      port: {{ .Values.containerPort}}
    initialDelaySeconds: 60
    periodSeconds: 5
{{- end }}
