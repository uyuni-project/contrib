**1. Create a virtual environment** This isolates your Python dependencies from the global system.

Bash
```
python3 -m venv venv
```
**2. Activate the virtual environment** _You must do this every time you work on the project or start the server._

Bash

```
# On macOS/Linux
source venv/bin/activate

# On Windows
venv\\Scripts\\activate

```

**4. Install the required dependencies**

Bash

```
pip install fastapi uvicorn pydantic requests

```

**5. Configure your Server URL** Open `main.py` in your text editor and update the `SUSE_MANAGER_URL` variable at the top of the file to point to your actual server:

Bash

```
export UYUNI_URL="https://your-server.com/rpc/api
```

_(Note: Keep the `/rpc/api` path at the end!)_

## 🏃‍♂️ Running the Gateway

Start the FastAPI server using Uvicorn:

Bash

```
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

```

## 📖 How to Use the Gateway

### 1. Access the Swagger UI

Open your web browser and navigate to: **http://127.0.0.1:8000/docs**

This will load the interactive API documentation. (If you navigate to the root `http://127.0.0.1:8000/`, it will automatically redirect you here).

### 2. Authenticate

1.  Click the green **Authorize** button at the top right of the page.
    
2.  Enter your SUSE Manager **Username** and **Password**.
    
3.  Click Authorize.
    
4.  The gateway will negotiate a session token with the XML-RPC backend and automatically inject it as a Bearer token into all subsequent requests you make in the UI.
    

### 3. Explore Built-in Endpoints

You can now click **Try it out** -> **Execute** on any of the pre-mapped endpoints like `/systems`, `/users`, `/channels`, and `/errata`.

### 4. Use the "Universal Executor"

Don't see the endpoint you need? You don't have to code it!

1.  Look up the method in the [SUSE Manager API Documentation](https://documentation.suse.com/suma/4.3/api/suse-manager/index.html) (e.g., `kickstart.profile.listProfiles`).
    
2.  Go to the **8. Universal API Executor** block in Swagger and click **Try it out**.
    
3.  Pass the method name and any required parameters (excluding the session token) in the JSON body:
    
    JSON
    
    ```
    {
      "method": "kickstart.profile.listProfiles",
      "params": []
    }
    
    ```
    
4.  Hit **Execute** to dynamically fetch the data.
    

## ⚠️ Security Note

For development purposes, this script uses `ssl._create_unverified_context()` to bypass strict SSL certificate verification. **Do not use this configuration in a production environment** without implementing proper internal certificate authority (CA) trusting.
