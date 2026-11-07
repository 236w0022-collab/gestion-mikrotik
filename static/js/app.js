async function cambiarServicio(accion, ip) {
    let url = accion === 'cortar' ? `/clientes/cortar?ip_cliente=${ip}` : `/clientes/reactivar?ip_cliente=${ip}`;
    try {
        let response = await fetch(url, { method: 'POST' });
        let data = await response.json();
        if (response.ok) {
            alert(data.mensaje);
            location.reload();
        } else {
            alert("Error: " + data.detail);
        }
    } catch (err) {
        alert("Error de conexión con el servidor.");
    }
}

async function registrarCliente(event) {
    event.preventDefault();
    let datos = {
        nombre: document.getElementById('reg_nombre').value,
        telefono: document.getElementById('reg_telefono').value || null,
        ip_estatica: document.getElementById('reg_ip').value,
        plan_id: parseInt(document.getElementById('reg_plan').value),
        fecha_corte: document.getElementById('reg_fecha').value
    };

    try {
        let response = await fetch('/clientes/registrar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });
        let data = await response.json();
        if (response.ok) {
            alert(data.mensaje);
            location.reload();
        } else {
            alert("Error: " + data.detail);
        }
    } catch (err) {
        alert("Error al conectar con el servidor.");
    }
}

async function actualizarCliente(event, id) {
    event.preventDefault();
    let planId = document.getElementById(`edit_plan_${id}`).value;
    let fecha = document.getElementById(`edit_fecha_${id}`).value;

    try {
        let response = await fetch(`/clientes/modificar/${id}?plan_id=${planId}&fecha_corte=${fecha}`, {
            method: 'POST'
        });
        let data = await response.json();
        if (response.ok) {
            alert(data.mensaje);
            location.reload();
        } else {
            alert("Error: " + data.detail);
        }
    } catch (err) {
        alert("Error al actualizar cliente.");
    }
}

async function eliminarCliente(id, nombre, ip) {
    if (!confirm(`¿Estás seguro de eliminar a ${nombre}?`)) return;

    try {
        let response = await fetch(`/clientes/eliminar/${id}?ip_cliente=${ip}`, {
            method: 'DELETE'
        });
        let data = await response.json();
        if (response.ok) {
            alert(data.mensaje);
            location.reload();
        } else {
            alert("Error: " + data.detail);
        }
    } catch (err) {
        alert("Error al eliminar cliente.");
    }
}
