{{/*
Expand the name of the chart.
*/}}
{{- define "onyx.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "onyx.fullname" -}}
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
{{- define "onyx.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "onyx.labels" -}}
helm.sh/chart: {{ include "onyx.chart" . }}
{{ include "onyx.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "onyx.selectorLabels" -}}
app.kubernetes.io/name: {{ include "onyx.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "onyx.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "onyx.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Set secret name - supports both direct call and dict with root context for tpl evaluation
Usage 1 (no tpl): {{ include "onyx.secretName" $secretContent }}
Usage 2 (with tpl): {{ include "onyx.secretName" (dict "secretContent" $secretContent "root" $root) }}
*/}}
{{- define "onyx.secretName" -}}
{{- if .secretContent }}
{{- /* Called with dict containing secretContent and root - use tpl for template evaluation */}}
{{- $secretName := default .secretContent.secretName .secretContent.existingSecret }}
{{- tpl $secretName .root }}
{{- else }}
{{- /* Called directly with secretContent - no tpl needed */}}
{{- default .secretName .existingSecret }}
{{- end }}
{{- end }}

{{/*
Create env vars from secrets
*/}}
{{- define "onyx.envSecrets" -}}
    {{- $root := . }}
    {{- range $secretSuffix, $secretContent := .Values.auth }}
    {{- if and (ne $secretContent.enabled false) ($secretContent.secretKeys) }}
    {{- range $name, $key := $secretContent.secretKeys }}
    {{- if $key }}
- name: {{ $name | upper | replace "-" "_" | quote }}
  valueFrom:
    secretKeyRef:
      name: {{ include "onyx.secretName" (dict "secretContent" $secretContent "root" $root) }}
      key: {{ default $name $key }}
    {{- end }}
    {{- end }}
    {{- end }}
    {{- end }}
{{- end }}

{{/*
Return the configured autoscaling engine; defaults to HPA when unset.
*/}}
{{- define "onyx.autoscaling.engine" -}}
{{- $engine := default "hpa" .Values.autoscaling.engine -}}
{{- $engine | lower -}}
{{- end }}
