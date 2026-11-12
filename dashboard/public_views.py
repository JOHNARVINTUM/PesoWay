from django.shortcuts import render


def home(request):
    return render(request, "public/home.html")


def developer_docs(request):
    return render(request, "public/developers.html")
