{{/*
Expand the name of the chart with cloak prefix
*/}}
{{- define "keycloak.name" -}}
cloak-{{- default .Chart.Name .Values.nameOverride | trunc 58 | trimSuffix "-" }}
{{- end }}

{{/*
Create a fullname for resources (with release name prefix)
*/}}
{{- define "keycloak.fullname" -}}
{{- if .Values.fullnameOverride }}
cloak-{{- .Values.fullnameOverride | trunc 58 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name (include "keycloak.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
