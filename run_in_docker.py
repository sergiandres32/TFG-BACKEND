#!/usr/bin/env python3
"""
Script: run_in_docker.py
Propósito:
  Ejecutar evaluaciones dentro de un contenedor Docker con límites de recursos.
  Previene que código malicioso o ineficiente consuma recursos del sistema.

Uso:
  python3 run_in_docker.py <codigo.c> <tests.json> [--memory 512m] [--cpus 1]
"""

import subprocess
import sys
import os
import argparse
from pathlib import Path


def build_docker_image(tag: str = "jutge:latest") -> bool:
    """Construye la imagen Docker."""
    print(f"Construyendo imagen Docker: {tag}")
    result = subprocess.run(
        ["docker", "build", "-t", tag, "."],
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    return result.returncode == 0


def get_absolute_path(path: str) -> str:
    """Convierte una ruta relativa a absoluta."""
    return str(Path(path).resolve())


def run_in_docker(code_file: str, tests_file: str, memory: str = "512m", cpus: str = "1") -> int:
    """Ejecuta el juez dentro de Docker.
    
    Args:
        code_file: ruta al archivo C
        tests_file: ruta al archivo JSON de pruebas
        memory: límite de memoria (ej: 512m, 1g)
        cpus: número de CPUs asignadas
    """
    
    # Verificar que los archivos existen
    if not os.path.exists(code_file):
        print(f"Error: Archivo {code_file} no encontrado")
        return 1
    
    if not os.path.exists(tests_file):
        print(f"Error: Archivo {tests_file} no encontrado")
        return 1
    
    # Convertir a rutas absolutas
    code_abs = get_absolute_path(code_file)
    tests_abs = get_absolute_path(tests_file)
    project_root = get_absolute_path(".")
    
    # Rutas relativas dentro del contenedor
    code_in_container = f"/submissions/{os.path.basename(code_file)}"
    tests_in_container = f"/test_cases/{os.path.basename(tests_file)}"
    
    print(f"Ejecutando en Docker...")
    print(f"  Código: {code_file}")
    print(f"  Pruebas: {tests_file}")
    print(f"  Memoria: {memory}")
    print(f"  CPUs: {cpus}")
    print()
    
    # Comando docker run con límites de recursos
    cmd = [
        "docker", "run",
        "--rm",                              # Eliminar contenedor al terminar
        f"--memory={memory}",                # Límite de memoria
        f"--cpus={cpus}",                   # Límite de CPUs
        "--network=none",                    # Sin acceso a red
        "-v", f"{code_abs}:{code_in_container}:ro",
        "-v", f"{tests_abs}:{tests_in_container}:ro",
        "-v", f"{project_root}/src:/judge/src:ro",
        "jutge:latest",
        code_in_container,
        tests_in_container
    ]
    
    print("Ejecutando contenedor...")
    result = subprocess.run(cmd)
    
    return result.returncode


def main(argv):
    parser = argparse.ArgumentParser(
        description="Ejecutar evaluaciones en Docker con límites de recursos"
    )
    parser.add_argument("code", help="Ruta al archivo C")
    parser.add_argument("tests", help="Ruta al archivo JSON de pruebas")
    parser.add_argument("--memory", default="512m", help="Límite de memoria (defecto: 512m)")
    parser.add_argument("--cpus", default="1", help="CPUs asignadas (defecto: 1)")
    parser.add_argument("--build", action="store_true", help="Construir imagen Docker antes")
    
    args = parser.parse_args(argv)
    
    # Verificar que Docker está disponible
    try:
        subprocess.run(["docker", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: Docker no está instalado o no es accesible")
        print("Instala Docker desde: https://www.docker.com/products/docker-desktop")
        return 1
    
    # Construir imagen si se solicita
    if args.build:
        if not build_docker_image():
            print("Error: Falló la construcción de la imagen Docker")
            return 1
    
    # Ejecutar en Docker
    return run_in_docker(args.code, args.tests, args.memory, args.cpus)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
