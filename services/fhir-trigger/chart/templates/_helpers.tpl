{{/*
Expand the name of the chart.
*/}}
{{- define "fhir-trigger.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "fhir-trigger.fullname" -}}
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
{{- define "fhir-trigger.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "fhir-trigger.labels" -}}
helm.sh/chart: {{ include "fhir-trigger.chart" . }}
{{ include "fhir-trigger.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "fhir-trigger.selectorLabels" -}}
app.kubernetes.io/name: {{ include "fhir-trigger.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "fhir-trigger.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "fhir-trigger.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the bootstrap server to use
*/}}
{{- define "fhir-trigger.kafka.bootstrap" -}}
{{- if .Values.kafka.bootstrap }}
{{- .Values.kafka.bootstrap }}
{{- else }}
{{- .Release.Name }}-kafka:9092
{{- end }}
{{- end }}

{{/*
Create the name of the fhir server to use
*/}}
{{- define "fhir-trigger.fhir.endpoint" -}}
{{- if .Values.fhir.endpoint }}
{{- .Values.fhir.endpoint }}
{{- else }}
{{- printf "http://%s-fhir:80/fhir-server/api/v4" .Release.Name }}
{{- end }}
{{- end }}