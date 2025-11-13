# En: portal_retenciones/views/auth/auth.py

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse

# Vista para manejar el POST del formulario de login
def login_view(request):
    
    # Solo reaccionamos si el método es POST (alguien envió el formulario)
    if request.method == 'POST':
        # 1. Obtenemos los datos del formulario (usando los 'name' que pusimos en el HTML)
        username_from_form = request.POST.get('username')
        password_from_form = request.POST.get('password')

        # 2. Autenticamos al usuario contra la base de datos de Django
        user = authenticate(request, username=username_from_form, password=password_from_form)

        # 3. Verificamos si el usuario es válido
        if user is not None:
            # 4. Si es válido, iniciamos la sesión
            login(request, user)
            
            # 5. Redirigimos a una página de "éxito" (la crearemos en el sig. paso)
            #    Por ahora, vamos a redirigir a una URL llamada 'menu'
            return redirect('menu')
        else:
            # 5b. Si no es válido, volvemos a la página de inicio (login)
            #    (Aquí podrías agregar un mensaje de error)
            return redirect('home')

    # Si alguien intenta acceder a /login/ directamente (GET), lo mandamos al inicio
    return redirect('home')


# Vista para cerrar la sesión
def logout_view(request):
    logout(request)
    # Después de cerrar sesión, lo mandamos de vuelta al inicio (login)
    return redirect('home')