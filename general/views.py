from django.shortcuts import render

from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import generic
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy

from general.models import Being_Type

# Create your views here.

def show_being_types(request):
  #return render_to_response("being_types.html",
  return render(request, "being_types.html",
    {'nodes':Being_Type.objects.all()},
    )
    #context_instance=RequestContext(request))
