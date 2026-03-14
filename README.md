# GitOps-to-VPS 

A streamlined, secure, and fully automated GitOps pipeline designed to validate, deliver, and monitor Docker containers on a VPS infrastructure. Known as "The Gatekeeper", this repository ensures that every deployment meets strict security, networking, and resource constraints before it ever reaches production.

##  Architecture & Features

This project utilizes GitHub Actions to form a robust, 4-stage CI/CD pipeline:
1. **Validation (`validate_deploy.py`)**: A Python-based validation agent that acts as the "Gatekeeper", parsing `docker-compose.yml` and Traefik labels to enforce rules such as domain routing, SSL certificate generation, Authelia authentication, and CPU/Memory limits.
2. **Deployment**: Securely transfers files via SSH and executes Docker pulls and container restarts cleanly, without downtime.
3. **Health-check**: Waits for the services to stabilize and verifies that all containers are actively running.
4. **Automated Rollback**: Restores the previous configuration automatically if the health-check fails.

##  Dashboard v2
Includes a premium real-time monitoring dashboard, designed with a dark glassmorphism aesthetic. It visualizes the current state of the infrastructure with:
- **Resource Usage**: Live CPU and Memory gauges per container (via `docker stats`).
- **Certificate Monitoring**: Automatic parsing of Traefik's `acme.json` to warn about expiring SSL certificates.
- **Service State**: Clear visualization of missing dependencies, routing misconfigurations, and unhealthy containers.
- **Deployment Timeline**: A history of recent CI/CD deployments directly from the server log.

<img width="1024" height="559" alt="image" src="https://github.com/user-attachments/assets/899e44a8-fc1f-475d-b647-81df01f768e9" />
