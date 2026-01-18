pipeline {
  agent any

  environment {
    IMAGE_REPO = "katiravan/mldevops"   		// match with image
    NAMESPACE  = "mldevopskatir"     // match your namespace.yml
    APP_NAME   = "mldevops"        // must match Deployment name + container name
    SERVICE    = "mldevops"    	// must match Service name
  }

  options { 
    timestamps()
  }

  stages {

    stage('Checkout') {
      steps {
        checkout scm
        bat 'git --version'
        bat 'docker --version'
        bat 'kubectl version --client=true'
      }
    }

    stage('Compute Tags') {
      steps {
        bat '''
          @echo on
          setlocal EnableDelayedExpansion

          set SHORTSHA=
          for /f %%i in ('git rev-parse --short=7 HEAD') do set SHORTSHA=%%i
          echo SHORTSHA=!SHORTSHA!

          rem If build is running on a git tag (e.g. v1.0.0), capture it
          for /f %%t in ('git describe --tags --exact-match 2^>nul') do set RELTAG=%%t
          echo RELTAG=!RELTAG!
        '''
      }
    }

    stage('QA (Lint + Unit Tests)') {
      steps {
        bat '''
          @echo on
          python --version
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest 

          if not exist reports mkdir reports
          python -m pytest -q --junitxml=reports\\test-results.xml
          dir reports
        '''
      }
      post {
        always {
          junit 'reports/test-results.xml'
          archiveArtifacts artifacts: 'reports/test-results.xml', fingerprint: true
        }
      }
    }

    stage('Build Image') {
      steps {
        bat '''
          @echo on
          setlocal EnableDelayedExpansion
          
          set SHORTSHA=
          for /f %%i in ('git rev-parse --short=7 HEAD') do set SHORTSHA=%%i
          docker build -t %IMAGE_REPO%:git-!SHORTSHA! .

          set RELTAG=
          for /f %%t in ('git describe --tags --exact-match 2^>nul') do set RELTAG=%%t

          if not "!RELTAG!"=="" (
          docker tag %IMAGE_REPO%:git-!SHORTSHA! %IMAGE_REPO%:!RELTAG!
          echo Release tag applied: !RELTAG!
          ) else (
          echo No release tag. Skipping SemVer tag.
        )
      endlocal
        '''
      }
    }

    stage('Push Image') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'registry-creds', usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
          bat '''
            @echo on
            setlocal EnableDelayedExpansion
            
            set SHORTSHA=
            for /f %%i in ('git rev-parse --short=7 HEAD') do set SHORTSHA=%%i

            echo %DOCKER_PASS% | docker login -u %DOCKER_USER% --password-stdin

            docker push %IMAGE_REPO%:git-!SHORTSHA!
            
            set RELTAG=
            for /f %%t in ('git describe --tags --exact-match 2^>nul') do set RELTAG=%%t

            if not "!RELTAG!"=="" (
              docker push %IMAGE_REPO%:!RELTAG!
              ) else (
              echo No release tag. Skipping push for SemVer tag.
            )
        endlocal
      '''
        }
      }
    }

    stage('Deploy to Kubernetes (Apply + Set Image)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            @echo on
            set KUBECONFIG=%KUBECONFIG_FILE%
            setlocal EnableDelayedExpansion
            
            rem Apply base manifests
            kubectl apply -f k8s\\namespace.yml
            kubectl apply -f k8s\\deployment.yml
            kubectl apply -f k8s\\service.yml

            rem Update image to immutable commit tag
            set SHORTSHA=
            for /f %%i in ('git rev-parse --short=7 HEAD') do set SHORTSHA=%%i
            
            kubectl -n %NAMESPACE% set image deploy/%APP_NAME% %APP_NAME%=%IMAGE_REPO%:git-!SHORTSHA!
            endlocal
          '''
        }
      }
    }

    stage('Rollout Gate (Must Succeed)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            @echo on
            set KUBECONFIG=%KUBECONFIG_FILE%

            kubectl -n %NAMESPACE% rollout status deploy/%APP_NAME% --timeout=180s
            kubectl -n %NAMESPACE% get pods -o wide
            kubectl -n %NAMESPACE% get svc
          '''
        }
      }
    }

    stage('Smoke Test (/health)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            @echo on
            set KUBECONFIG=%KUBECONFIG_FILE%

            rem Call service inside cluster
            kubectl -n %NAMESPACE% run curl --rm -i --restart=Never --image=curlimages/curl -- ^
              curl -sS http://%SERVICE%:8000/health
          '''
        }
      }
    }

   stage('Load Test (k6)') {
  steps {
    withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
      bat '''
        @echo on
        set KUBECONFIG=%KUBECONFIG_FILE%

        kubectl -n %NAMESPACE% delete pod k6 --ignore-not-found

        kubectl -n %NAMESPACE% create configmap k6-script --from-file=loadtest\\k6.js --dry-run=client -o yaml | kubectl apply -f -

        > k6-pod.yaml (
          echo apiVersion: v1
          echo kind: Pod
          echo metadata:
          echo   name: k6
          echo   namespace: %NAMESPACE%
          echo spec:
          echo   restartPolicy: Never
          echo   containers:
          echo   - name: k6
          echo     image: grafana/k6:latest
          echo     env:
          echo     - name: BASE_URL
          echo       value: "http://%SERVICE%:8000"
          echo     args: ["run","/scripts/k6.js"]
          echo     volumeMounts:
          echo     - name: k6-scripts
          echo       mountPath: /scripts
          echo   volumes:
          echo   - name: k6-scripts
          echo     configMap:
          echo       name: k6-script
        )

        kubectl apply -f k6-pod.yaml
        kubectl -n %NAMESPACE% wait --for=condition=Ready pod/k6 --timeout=60s
        kubectl -n %NAMESPACE% logs -f pod/k6
        kubectl -n %NAMESPACE% delete pod k6 --ignore-not-found
      '''
    }
  }
}


  post {
    always {
      archiveArtifacts artifacts: 'k8s/**/*,loadtest/**/*,Dockerfile,Jenkinsfile,requirements.txt,README.md', fingerprint: true
    }
  }
}
