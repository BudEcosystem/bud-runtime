{{/*
Expand the name of the chart.
*/}}
{{- define "inference-stack.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "inference-stack.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "inference-stack.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "inference-stack.labels" -}}
helm.sh/chart: {{ include "inference-stack.chart" . }}
{{ include "inference-stack.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "inference-stack.selectorLabels" -}}
app.kubernetes.io/name: {{ include "inference-stack.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use for AIBrix
*/}}
{{- define "inference-stack.aibrix.serviceAccountName" -}}
{{- if .Values.aibrix.serviceAccount.create }}
{{- default (printf "%s-%s" (include "inference-stack.fullname" .) "aibrix") .Values.aibrix.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.aibrix.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the service account to use for VLLM
*/}}
{{- define "inference-stack.vllm.serviceAccountName" -}}
{{- if .Values.vllm.serviceAccount.create }}
{{- default (printf "%s-%s" (include "inference-stack.fullname" .) "vllm") .Values.vllm.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.vllm.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Get the namespace
*/}}
{{- define "inference-stack.namespace" -}}
{{- default .Release.Namespace .Values.global.namespace }}
{{- end }}