{{- define "bud.ingress.hosts.budadmin" -}}
{{- if .Values.ingress.hosts.budadmin }}
{{- .Values.ingress.hosts.budadmin }}
{{- else }}
{{- printf "admin.%s" .Values.ingress.hosts.root }}
{{- end }}
{{- end }}
{{- define "bud.ingress.hosts.budcustomer" -}}
{{- if .Values.ingress.hosts.budcustomer }}
{{- .Values.ingress.hosts.budcustomer }}
{{- else }}
{{- printf "customer.%s" .Values.ingress.hosts.root }}
{{- end }}
{{- end }}
{{- define "bud.ingress.hosts.budplayground" -}}
{{- if .Values.ingress.hosts.budplayground }}
{{- .Values.ingress.hosts.budplayground }}
{{- else }}
{{- printf "playground.%s" .Values.ingress.hosts.root }}
{{- end }}
{{- end }}
{{- define "bud.ingress.hosts.budapp" -}}
{{- if .Values.ingress.hosts.budapp }}
{{- .Values.ingress.hosts.budapp }}
{{- else }}
{{- printf "app.%s" .Values.ingress.hosts.root }}
{{- end }}
{{- end }}
{{- define "bud.ingress.hosts.budgateway" -}}
{{- if .Values.ingress.hosts.budgateway }}
{{- .Values.ingress.hosts.budgateway }}
{{- else }}
{{- printf "gateway.%s" .Values.ingress.hosts.root }}
{{- end }}
{{- end }}
{{- define "bud.ingress.hosts.budask" -}}
{{- if .Values.ingress.hosts.budask }}
{{- .Values.ingress.hosts.budask }}
{{- else }}
{{- printf "ask.%s" .Values.ingress.hosts.root }}
{{- end }}
{{- end }}
{{- define "bud.ingress.hosts.novuapi" -}}
{{- if .Values.ingress.hosts.novuapi }}
{{- .Values.ingress.hosts.novuapi }}
{{- else }}
{{- printf "api.novu.%s" .Values.ingress.hosts.root }}
{{- end }}
{{- end }}
{{- define "bud.ingress.hosts.novuws" -}}
{{- if .Values.ingress.hosts.novuws }}
{{- .Values.ingress.hosts.novuws }}
{{- else }}
{{- printf "ws.novu.%s" .Values.ingress.hosts.root }}
{{- end }}
{{- end }}
{{- define "bud.ingress.hosts.s3" -}}
{{- if .Values.ingress.hosts.s3 }}
{{- .Values.ingress.hosts.s3 }}
{{- else }}
{{- printf "s3.%s" .Values.ingress.hosts.root }}
{{- end }}
{{- end }}
{{- define "bud.ingress.hosts.mcpgateway" -}}
{{- if .Values.ingress.hosts.mcpgateway }}
{{- .Values.ingress.hosts.mcpgateway }}
{{- else }}
{{- printf "mcpgateway.%s" .Values.ingress.hosts.root }}
{{- end }}
{{- end }}
{{- define "bud.ingress.hosts.onyx" -}}
{{- if .Values.ingress.hosts.onyx }}
{{- .Values.ingress.hosts.onyx }}
{{- else }}
{{- printf "chat.%s" .Values.ingress.hosts.root }}
{{- end }}
{{- end }}

{{- define "bud.ingress.url.mcpgateway" -}}
{{- if ne .Values.ingress.https "disabled" }}
{{- printf "https://%s" (include "bud.ingress.hosts.mcpgateway" $) }}
{{- else }}
{{- printf "http://%s" (include "bud.ingress.hosts.mcpgateway" $) }}
{{- end }}
{{- end }}
{{- define "bud.ingress.url.budadmin" -}}
{{- if ne .Values.ingress.https "disabled" }}
{{- printf "https://%s" (include "bud.ingress.hosts.budadmin" $) }}
{{- else }}
{{- printf "http://%s" (include "bud.ingress.hosts.budadmin" $) }}
{{- end }}
{{- end }}
{{- define "bud.ingress.url.budcustomer" -}}
{{- if ne .Values.ingress.https "disabled" }}
{{- printf "https://%s" (include "bud.ingress.hosts.budcustomer" $) }}
{{- else }}
{{- printf "http://%s" (include "bud.ingress.hosts.budcustomer" $) }}
{{- end }}
{{- end }}
{{- define "bud.ingress.url.budplayground" -}}
{{- if ne .Values.ingress.https "disabled" }}
{{- printf "https://%s" (include "bud.ingress.hosts.budplayground" $) }}
{{- else }}
{{- printf "http://%s" (include "bud.ingress.hosts.budplayground" $) }}
{{- end }}
{{- end }}
{{- define "bud.ingress.url.budapp" -}}
{{- if ne .Values.ingress.https "disabled" }}
{{- printf "https://%s" (include "bud.ingress.hosts.budapp" $) }}
{{- else }}
{{- printf "http://%s" (include "bud.ingress.hosts.budapp" $) }}
{{- end }}
{{- end }}
{{- define "bud.ingress.url.budgateway" -}}
{{- if ne .Values.ingress.https "disabled" }}
{{- printf "https://%s" (include "bud.ingress.hosts.budgateway" $) }}
{{- else }}
{{- printf "http://%s" (include "bud.ingress.hosts.budgateway" $) }}
{{- end }}
{{- end }}
{{- define "bud.ingress.url.budask" -}}
{{- if ne .Values.ingress.https "disabled" }}
{{- printf "https://%s" (include "bud.ingress.hosts.budask" $) }}
{{- else }}
{{- printf "http://%s" (include "bud.ingress.hosts.budask" $) }}
{{- end }}
{{- end }}
{{- define "bud.ingress.url.novuapi" -}}
{{- if ne .Values.ingress.https "disabled" }}
{{- printf "https://%s" (include "bud.ingress.hosts.novuapi" $) }}
{{- else }}
{{- printf "http://%s" (include "bud.ingress.hosts.novuapi" $) }}
{{- end }}
{{- end }}
{{- define "bud.ingress.url.novuws" -}}
{{- if ne .Values.ingress.https "disabled" }}
{{- printf "https://%s" (include "bud.ingress.hosts.novuws" $) }}
{{- else }}
{{- printf "http://%s" (include "bud.ingress.hosts.novuws" $) }}
{{- end }}
{{- end }}
{{- define "bud.ingress.url.s3" -}}
{{- if ne .Values.ingress.https "disabled" }}
{{- printf "https://%s" (include "bud.ingress.hosts.s3" $) }}
{{- else }}
{{- printf "http://%s" (include "bud.ingress.hosts.s3" $) }}
{{- end }}
{{- end }}
{{- define "bud.ingress.url.onyx" -}}
{{- if ne .Values.ingress.https "disabled" }}
{{- printf "https://%s" (include "bud.ingress.hosts.onyx" $) }}
{{- else }}
{{- printf "http://%s" (include "bud.ingress.hosts.onyx" $) }}
{{- end }}
{{- end }}


{{- define "bud.externalServices.minio.endpoint" -}}
{{- if .Values.externalServices.minio.endpoint }}
{{- print .Values.externalServices.minio.endpoint  }}
{{- else }}
{{- printf "%s-minio.%s:9000" .Release.Name .Release.Namespace }}
{{- end }}
{{- end }}
{{- define "bud.externalServices.minio.auth.accessKey" -}}
{{- if .Values.externalServices.minio.auth.accessKey }}
{{- print .Values.externalServices.minio.auth.accessKey  }}
{{- else }}
{{- print .Values.minio.auth.rootUser  }}
{{- end }}
{{- end }}
{{- define "bud.externalServices.minio.auth.secretKey" -}}
{{- if .Values.externalServices.minio.auth.secretKey }}
{{- print .Values.externalServices.minio.auth.secretKey  }}
{{- else }}
{{- print .Values.minio.auth.rootPassword  }}
{{- end }}
{{- end }}

{{- define "bud.externalServices.postgresql.host" -}}
{{- if .Values.externalServices.postgresql.host }}
{{- print .Values.externalServices.postgresql.host  }}
{{- else }}
{{- printf "%s-postgresql.%s" .Release.Name .Release.Namespace }}
{{- end }}
{{- end }}

{{/*
Node selector for microservices
Replaces global nodeSelector with per-service nodeSelector (per-service takes precedence)
Only applies non-empty nodeSelector values
Usage: {{ include "bud.nodeSelector" (dict "service" .Values.microservices.budapp "global" .Values.global "context" $) }}
*/}}
{{- define "bud.nodeSelector" -}}
{{- $service := .service -}}
{{- $global := .global -}}
{{- if and $service.nodeSelector (gt (len $service.nodeSelector) 0) -}}
{{- toYaml $service.nodeSelector }}
{{- else if and $global.nodeSelector (gt (len $global.nodeSelector) 0) -}}
{{- toYaml $global.nodeSelector }}
{{- end }}
{{- end }}

{{/*
Affinity for microservices
Replaces global affinity with per-service affinity (per-service takes precedence)
Only applies non-empty affinity values
Usage: {{ include "bud.affinity" (dict "service" .Values.microservices.budapp "global" .Values.global "context" $) }}
*/}}
{{- define "bud.affinity" -}}
{{- $service := .service -}}
{{- $global := .global -}}
{{- if and $service.affinity (gt (len $service.affinity) 0) -}}
{{- toYaml $service.affinity }}
{{- else if and $global.affinity (gt (len $global.affinity) 0) -}}
{{- toYaml $global.affinity }}
{{- end }}
{{- end }}

{{/*
HPA (Horizontal Pod Autoscaler) template for microservices
Creates a standardized HPA resource with CPU and memory based scaling
Usage: {{ include "bud.hpa" (dict "serviceName" "budapp" "Values" .Values "Release" .Release) }}
*/}}
{{- define "bud.hpa" -}}
{{- $serviceName := .serviceName -}}
{{- $service := index .Values.microservices $serviceName -}}
{{- if and $service.autoscaling $service.autoscaling.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ .Release.Name }}-{{ $serviceName }}
  labels:
    app: {{ .Release.Name }}-{{ $serviceName }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ .Release.Name }}-{{ $serviceName }}
  minReplicas: {{ $service.autoscaling.minReplicas | default 1 }}
  maxReplicas: {{ $service.autoscaling.maxReplicas | default 3 }}
  metrics:
    {{- if $service.autoscaling.targetCPUUtilizationPercentage }}
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ $service.autoscaling.targetCPUUtilizationPercentage }}
    {{- end }}
    {{- if $service.autoscaling.targetMemoryUtilizationPercentage }}
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: {{ $service.autoscaling.targetMemoryUtilizationPercentage }}
    {{- end }}
  behavior:
    scaleDown:
      stabilizationWindowSeconds: {{ $service.autoscaling.scaleDownStabilizationSeconds | default 300 }}
      policies:
        - type: Percent
          value: 50
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: {{ $service.autoscaling.scaleUpStabilizationSeconds | default 30 }}
      policies:
        - type: Percent
          value: 100
          periodSeconds: 15
        - type: Pods
          value: 2
          periodSeconds: 15
      selectPolicy: Max
{{- end }}
{{- end }}
