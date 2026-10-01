from django.urls import path
from . import views

urlpatterns = [
    path("reportes/", views.ReportDashboardView.as_view(), name="report_dashboard"),
    path("reportes/exportar/pdf/", views.ReportExportView.as_view(fmt="pdf"), name="report_pdf"),
    path("reportes/exportar/excel/", views.ReportExportView.as_view(fmt="excel"), name="report_excel"),
]