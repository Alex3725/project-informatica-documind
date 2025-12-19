# 1. Immagine Node
FROM node:20-bullseye

# 2. Crea cartella app
WORKDIR /app

# 3. Copia package.json e package-lock.json per caching
COPY package*.json ./
RUN npm install

# 4. Copia tutto il resto
COPY . .

# 5. Espone porta SvelteKit
EXPOSE 5173

# 6. Comando di avvio (dev server accessibile da host)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
