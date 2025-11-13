{{/*
Expand the name of the chart.
*/}}
{{- define "studio.bud.name" -}}
{{- include "cloudpirates.name" . -}}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "studio.bud.fullname" -}}
{{- include "cloudpirates.fullname" . -}}
{{- end }}
