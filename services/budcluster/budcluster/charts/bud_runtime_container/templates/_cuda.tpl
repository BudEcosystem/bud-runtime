{{- define "bud-runtime-container.cuda-container" }}
- name: cuda-container
  image: {{ .device.image }}
  imagePullPolicy: {{ $.Values.pullPolicy }}
  ports:
    - containerPort: {{ $.Values.containerPort }}
  volumeMounts:
    - name: model-registry
      mountPath: /data/models-registry
      readOnly: false
  resources:
    requests:
      nvidia.com/gpu: {{ .device.tp_size }}
    limits:
      nvidia.com/gpu: {{ .device.tp_size }}
  {{- if .device.envs }}
  env:
  {{- range $key, $value := .device.envs }}
  - name: {{ $key }}
    value: {{ $value | quote }}
  {{- end }}
  {{- end }}
  command:
  - python3
  - -m
  - vllm.entrypoints.openai.api_server
  {{- if .device.args }}
  args:
  {{- range $key, $value := .device.args }}
  - {{ $value }}
  {{- end }}
  - --uvicorn-log-level
  - warning
  {{- end }}
  livenessProbe:
    httpGet:
      path: /health
      port: {{ $.Values.containerPort }}
    initialDelaySeconds: 120
    periodSeconds: 30
    failureThreshold: 20
  readinessProbe:
    httpGet:
      path: /health
      port: {{ $.Values.containerPort }}
    initialDelaySeconds: 60
    periodSeconds: 5
  startupProbe:
    httpGet:
      path: /health
      port: {{ $.Values.containerPort }}
      scheme: HTTP
    failureThreshold: 200
    periodSeconds: 30
    successThreshold: 1
    timeoutSeconds: 1
{{- end }}
