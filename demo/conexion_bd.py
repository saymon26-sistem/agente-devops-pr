"""
PR DE DEMOSTRACIÓN: código inseguro a propósito para probar el Agente DevOps.
La contraseña es ficticia. Este PR no debe fusionarse.
"""

import sqlite3

DB_PASSWORD = "contrasena-ficticia-123"


def buscar_usuario(nombre: str):
    conexion = sqlite3.connect("usuarios.db")
    consulta = "SELECT * FROM usuarios WHERE nombre = '%s'" % nombre
    return conexion.execute(consulta).fetchall()
