

pipeline {
  agent any

    tools {
  git 'Default'
  }

  environment {
    IMAGE_REPO = "katiravan/mldevops"     // Docker Hub repo
    NAMESPACE  = "mldevopskatir"          // k8s namespace
    APP_NAME   = "mldevops"              // Deployment name AND container name in deployment.yml
    SERVICE    = "mldevops"              // Service name
  }

  options { timestamps() }

  stages {

    stage('Checkout') {
      steps {
        checkout scm
        bat 'git --version'
        bat 'docker --version'
        bat 'kubectl version --client=true'
        bat 'git status'
        bat 'git rev-parse HEAD'
      }
    }

   stage('Compute Tags') {
  steps {
    script {
      env.SHORTSHA = bat(returnStdout: true, script: '@echo off\r\ngit rev-parse --short=7 HEAD').trim()

      def s = bat(returnStatus: true, script: '@echo off\r\ngit describe --tags --exact-match 1> .reltag.txt 2>nul')
      env.RELTAG = (s == 0) ? readFile('.reltag.txt').trim() : ''
    }
    bat '@echo on\necho SHORTSHA=%SHORTSHA%\necho RELTAG=%RELTAG%'
  }
}

    stage('QA (Unit Tests)') {
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
    script {
      if (!(env.SHORTSHA ==~ /^[0-9a-f]{7}$/)) {
        error("SHORTSHA invalid. Expected 7-hex, got: '${env.SHORTSHA}'")
      }
      if (env.RELTAG && !(env.RELTAG ==~ /^[0-9A-Za-z._-]+$/)) {
        error("RELTAG invalid. Got: '${env.RELTAG}'")
      }
    }

    bat '''
      @echo on
      echo Building image: "%IMAGE_REPO%:git-%SHORTSHA%"
      docker build -t "%IMAGE_REPO%:git-%SHORTSHA%" .

      if not "%RELTAG%"=="" (
        echo Applying release tag: %RELTAG%
        docker tag "%IMAGE_REPO%:git-%SHORTSHA%" "%IMAGE_REPO%:%RELTAG%"
      ) else (
        echo No release tag. Skipping SemVer tag.
      )
    '''
  }
}

    stage('Push Image') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'registry-creds', usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
          bat '''
            @echo on
            echo %DOCKER_PASS% | docker login -u %DOCKER_USER% --password-stdin

            docker push %IMAGE_REPO%:git-%SHORTSHA%

            if not "%RELTAG%"=="" (
              docker push %IMAGE_REPO%:%RELTAG%
            ) else (
              echo No release tag. Skipping push for SemVer tag.
            )
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

            kubectl apply -f k8s\\namespace.yml
            kubectl apply -f k8s\\deployment.yml
            kubectl apply -f k8s\\service.yml

            echo Setting image to: %IMAGE_REPO%:git-%SHORTSHA%
            kubectl -n %NAMESPACE% set image deployment/%APP_NAME% %APP_NAME%=%IMAGE_REPO%:git-%SHORTSHA%
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

            kubectl -n %NAMESPACE% rollout status deployment/%APP_NAME% --timeout=180s
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
        setlocal EnableDelayedExpansion

        rem --- Cleanup previous run (ignore if not found)
        kubectl -n %NAMESPACE% delete job k6 --ignore-not-found
        kubectl -n %NAMESPACE% delete configmap k6-script --ignore-not-found

        rem --- Create/Apply ConfigMap from repo file (NO PIPE)
        if not exist "%WORKSPACE%\\loadtest\\k6.js" (
          echo ERROR: %WORKSPACE%\\loadtest\\k6.js not found
          dir "%WORKSPACE%\\loadtest"
          exit /b 1
        )

        kubectl -n %NAMESPACE% create configmap k6-script --from-file=k6.js="%WORKSPACE%\\loadtest\\k6.js" --dry-run=client -o yaml > k6-configmap.yaml
        kubectl -n %NAMESPACE% apply -f k6-configmap.yaml

        rem --- Write Job manifest
        > k6-job.yaml (
          echo apiVersion: batch/v1
          echo kind: Job
          echo metadata:
          echo   name: k6
          echo   namespace: %NAMESPACE%
          echo spec:
          echo   backoffLimit: 0
          echo   template:
          echo     metadata:
          echo       labels:
          echo         app: k6
          echo     spec:
          echo       restartPolicy: Never
          echo       containers:
          echo       - name: k6
          echo         image: grafana/k6:latest
          echo         env:
          echo         - name: BASE_URL
          echo           value: "http://%SERVICE%:8000"
          echo         args: ["run","/scripts/k6.js"]
          echo         volumeMounts:
          echo         - name: k6-scripts
          echo           mountPath: /scripts
          echo       volumes:
          echo       - name: k6-scripts
          echo         configMap:
          echo           name: k6-script
        )

        kubectl -n %NAMESPACE% apply -f k6-job.yaml

        rem --- Wait for Pod to be Ready (gives better errors if stuck in ContainerCreating)
        kubectl -n %NAMESPACE% wait --for=condition=Ready pod -l app=k6 --timeout=120s
        if errorlevel 1 (
          echo ERROR: k6 pod not Ready (likely image pull / volume mount / node issue)
          kubectl -n %NAMESPACE% get pod -l app=k6 -o wide
          kubectl -n %NAMESPACE% describe pod -l app=k6
          kubectl -n %NAMESPACE% get events --sort-by=.lastTimestamp
          exit /b 1
        )

        rem --- Stream logs
        for /f %%P in ('kubectl -n %NAMESPACE% get pod -l app=k6 -o jsonpath^="{.items[0].metadata.name}"') do set K6POD=%%P
        kubectl -n %NAMESPACE% logs -f !K6POD!

        rem --- Wait for Job completion (replaces custom FOR loop)
        kubectl -n %NAMESPACE% wait --for=condition=complete job/k6 --timeout=600s
        if errorlevel 1 (
          echo ERROR: k6 job did not complete within timeout.
          kubectl -n %NAMESPACE% describe job k6
          kubectl -n %NAMESPACE% describe pod -l app=k6
          kubectl -n %NAMESPACE% get events --sort-by=.lastTimestamp
          exit /b 1
        )

        rem --- Check exit code from pod container termination
        set K6_EXIT=
        for /f %%E in ('kubectl -n %NAMESPACE% get pod !K6POD! -o jsonpath^="{.status.containerStatuses[0].state.terminated.exitCode}"') do set K6_EXIT=%%E
        echo K6 exit code: !K6_EXIT!

        if not "!K6_EXIT!"=="0" (
          echo ERROR: k6 failed thresholds/tests.
          kubectl -n %NAMESPACE% describe pod !K6POD!
          exit /b 1
        )

        rem --- Cleanup
        kubectl -n %NAMESPACE% delete job k6 --ignore-not-found
        kubectl -n %NAMESPACE% delete configmap k6-script --ignore-not-found

        endlocal
      '''
    }
  }
}
  }

  post {
    always {
      archiveArtifacts artifacts: 'k8s/**/*,loadtest/**/*,Dockerfile,Jenkinsfile,requirements.txt,README.md', fingerprint: true
    }
  }
}
