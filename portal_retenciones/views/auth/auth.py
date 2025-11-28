# En: portal_retenciones/views/auth/auth.py

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse

# Vista para manejar el POST del formulario de login
def login_view(request):
    
    # Solo reaccionamos si el método es POST (alguien envió el formulario)
    if request.method == 'POST':
        # 1. Obtenemos los datos del formulario
        username_from_form = request.POST.get('username')
        password_from_form = request.POST.get('password')

        # 2. Autenticamos al usuario contra la base de datos de Django
        user = authenticate(request, username=username_from_form, password=password_from_form)

        # 3. Verificamos si el usuario es válido
        if user is not None:
            # 4. Si es válido, iniciamos la sesión
            login(request, user)
            
            # 5. Redirigimos a la página de menú
            return redirect('menu')
        else:
            # 5b. Si no es válido, mostramos mensaje de error
            return render(request, 'login.html', {
                'error': 'Usuario o contraseña incorrectos. Por favor, intenta de nuevo.'
            })

    # Si alguien intenta acceder a /login/ directamente (GET), lo mandamos al inicio
    return redirect('home')


# Vista para cerrar la sesión
def logout_view(request):
    logout(request)
    # Después de cerrar sesión, lo mandamos de vuelta al inicio (login)
    return redirect('home')