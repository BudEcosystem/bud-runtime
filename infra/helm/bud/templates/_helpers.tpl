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


{{- define "bud.ingress.url.budadmin" -}}
{{- if .Values.ingress.httpsEnabled }}
{{- printf "https://%s" (include "bud.ingress.hosts.budadmin" $) }}
{{- else }}
{{- printf "http://%s" (include "bud.ingress.hosts.budadmin" $) }}
{{- end }}
{{- end }}
{{- define "bud.ingress.url.budcustomer" -}}
{{- if .Values.ingress.httpsEnabled }}
{{- printf "https://%s" (include "bud.ingress.hosts.budcustomer" $) }}
{{- else }}
{{- printf "http://%s" (include "bud.ingress.hosts.budcustomer" $) }}
{{- end }}
{{- end }}
{{- define "bud.ingress.url.budplayground" -}}
{{- if .Values.ingress.httpsEnabled }}
{{- printf "https://%s" (include "bud.ingress.hosts.budplayground" $) }}
{{- else }}
{{- printf "http://%s" (include "bud.ingress.hosts.budplayground" $) }}
{{- end }}
{{- end }}
{{- define "bud.ingress.url.budapp" -}}
{{- if .Values.ingress.httpsEnabled }}
{{- printf "https://%s" (include "bud.ingress.hosts.budapp" $) }}
{{- else }}
{{- printf "http://%s" (include "bud.ingress.hosts.budapp" $) }}
{{- end }}
{{- end }}
{{- define "bud.ingress.url.budgateway" -}}
{{- if .Values.ingress.httpsEnabled }}
{{- printf "https://%s" (include "bud.ingress.hosts.budgateway" $) }}
{{- else }}
{{- printf "http://%s" (include "bud.ingress.hosts.budgateway" $) }}
{{- end }}
{{- end }}
{{- define "bud.ingress.url.budask" -}}
{{- if .Values.ingress.httpsEnabled }}
{{- printf "https://%s" (include "bud.ingress.hosts.budask" $) }}
{{- else }}
{{- printf "http://%s" (include "bud.ingress.hosts.budask" $) }}
{{- end }}
{{- end }}
{{- define "bud.ingress.url.novuapi" -}}
{{- if .Values.ingress.httpsEnabled }}
{{- printf "https://%s" (include "bud.ingress.hosts.novuapi" $) }}
{{- else }}
{{- printf "http://%s" (include "bud.ingress.hosts.novuapi" $) }}
{{- end }}
{{- end }}
{{- define "bud.ingress.url.novuws" -}}
{{- if .Values.ingress.httpsEnabled }}
{{- printf "https://%s" (include "bud.ingress.hosts.novuws" $) }}
{{- else }}
{{- printf "http://%s" (include "bud.ingress.hosts.novuws" $) }}
{{- end }}
{{- end }}
