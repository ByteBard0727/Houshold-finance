from django.shortcuts import render

# Create your views here.
from django.http import HttpResponse

def breakdown(request):
    return HttpResponse("this will be the are with all the graphs and diagrams for different time periods")

