// Función para marcar el elemento activo del menú según la URL actual
function setActiveMenuItem() {
    // Obtener la ruta actual (pathname)
    const currentPath = window.location.pathname;
    
    // Seleccionar todos los enlaces del sidebar
    const menuLinks = document.querySelectorAll('.sidebar a');
    
    menuLinks.forEach(link => {
        // Obtener el href del enlace
        const linkPath = link.getAttribute('href');
        
        // Si el href coincide con la ruta actual, marcar como activo
        if (linkPath === currentPath || currentPath.endsWith(linkPath)) {
            link.parentElement.classList.add('active-item');
        } else {
            link.parentElement.classList.remove('active-item');
        }
    });
}

// Ejecutar cuando la página cargue completamente
document.addEventListener('DOMContentLoaded', function() {
    setActiveMenuItem();
});