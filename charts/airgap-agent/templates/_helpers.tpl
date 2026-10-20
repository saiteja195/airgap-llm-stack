{{- define "airgap.labels" -}}
app.kubernetes.io/name: airgap-agent
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "airgap.selector" -}}
app.kubernetes.io/name: airgap-agent
app.kubernetes.io/instance: {{ .ctx.Release.Name }}
app.kubernetes.io/component: {{ .c }}
{{- end -}}

{{- define "airgap.image" -}}
{{ .repository }}:{{ .tag }}
{{- end -}}

{{- define "airgap.secretName" -}}
{{ default (printf "%s-agent" .Release.Name) .Values.secret.existingSecret }}
{{- end -}}
